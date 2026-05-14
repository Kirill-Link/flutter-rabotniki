from datetime import date

from django.core.cache import cache
from django.utils.crypto import get_random_string
from django.template.context_processors import request
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Patient, Visit, VisitFile, PatientNote, TreatmentTypeOption, CapSystemOption, Parent


class ParentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = ['id', 'first_name', 'last_name', 'middle_name', 'phone', 'email']


class PatientCreateSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(write_only=True)
    parent_first_name = serializers.CharField(write_only=True)
    parent_last_name = serializers.CharField(write_only=True)
    parent_middle_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    parent_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    first_note = serializers.CharField(write_only=True, required=False, allow_blank=True)

    generated_password = serializers.SerializerMethodField()
    qr_image = serializers.ImageField(source='qr_code.image', read_only=True)
    parent = ParentShortSerializer(read_only=True)

    class Meta:
        model = Patient
        exclude = ['doctor', 'external_id']

    def create(self, validated_data):
        phone = validated_data.pop('phone')

        p_first_name = validated_data.pop('parent_first_name')
        p_last_name = validated_data.pop('parent_last_name')
        p_middle_name = validated_data.pop('parent_middle_name', '')
        p_email = validated_data.pop('parent_email', '')
        first_note_text = validated_data.pop('first_note', None)

        parent, created = Parent.objects.get_or_create(
            phone=phone,
            defaults={
                'first_name': p_first_name,
                'last_name': p_last_name,
                'middle_name': p_middle_name,
                'email': p_email or '',
            }
        )
        parent.first_name = p_first_name
        parent.last_name = p_last_name
        parent.middle_name = p_middle_name or ''
        parent.email = p_email or ''
        raw_password = get_random_string(8)
        parent.set_password(raw_password)
        parent.save()

        request = self.context.get('request')
        doctor = request.user if request else None

        validated_data.pop('doctor', None)

        patient = Patient.objects.create(parent=parent,doctor=doctor, **validated_data)

        patient._raw_password = raw_password

        cache.set(f'qr_sheet_pwd_{patient.id}', raw_password, timeout=300)

        if first_note_text:
            PatientNote.objects.create(patient=patient, text=first_note_text)

        return patient

    @extend_schema_field(str)
    def get_generated_password(self, obj):
        return getattr(obj, '_raw_password', None)

class PatientUpdateSerializer(serializers.ModelSerializer):
    parent_phone = serializers.CharField(source='parent.phone', read_only=True)
    parent_last_name = serializers.CharField(write_only=True, required=False)
    parent_first_name = serializers.CharField(write_only=True, required=False)
    parent_middle_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    parent_phone_write = serializers.CharField(write_only=True, required=False)
    parent_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Patient
        fields = [
            'parent_phone', 'parent_last_name', 'parent_first_name', 'parent_middle_name', 'parent_phone_write', 'parent_email',
            'last_name', 'first_name', 'middle_name',
            'birth_date', 'patient_photo', 'treatment_start_date',
            'treatment_stage', 'caps_count', 'change_cycle', 'status'
        ]

    def update(self, instance, validated_data):
        parent_data = {}
        for key in ('parent_last_name', 'parent_first_name', 'parent_middle_name', 'parent_phone_write', 'parent_email'):
            if key in validated_data:
                parent_data[key] = validated_data.pop(key)
        if 'parent_phone' in validated_data:
            validated_data.pop('parent_phone')
        parent = instance.parent
        if parent and parent_data:
            if parent_data.get('parent_last_name') is not None:
                parent.last_name = parent_data['parent_last_name']
            if parent_data.get('parent_first_name') is not None:
                parent.first_name = parent_data['parent_first_name']
            if 'parent_middle_name' in parent_data:
                parent.middle_name = parent_data['parent_middle_name'] or ''
            if parent_data.get('parent_phone_write'):
                parent.phone = parent_data['parent_phone_write']
            if 'parent_email' in parent_data:
                parent.email = parent_data['parent_email'] or ''
            parent.save()
        return super().update(instance, validated_data)


class ParentChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Пароли не совпадают."})
        return attrs

class PatientNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientNote
        fields = ['id', 'patient', 'text', 'created_at']


class PatientDetailSerializer(serializers.ModelSerializer):
    notes = PatientNoteSerializer(many=True, read_only=True)
    parent = ParentShortSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()
    next_visit = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = "__all__"

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'date': {'type': 'string', 'format': 'date'},
            'time': {'type': 'string', 'nullable': True},
        }
    })
    def get_next_visit(self, obj):
        # ближайший будущий неподтверждённый визит этого пациента
        visit = obj.visits.filter(
            date__gte=date.today(),
            is_confirmed=False
        ).order_by('date', 'time').first()

        if not visit:
            return None

        return {
            "date": visit.date.isoformat(),
            "time": visit.time.strftime("%H:%M") if visit.time else None,
        }

class VisitFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitFile
        fields = ['id', 'file', 'uploaded_at']

class VisitSerializer(serializers.ModelSerializer):
    files = VisitFileSerializer(many=True, read_only=True)
    patient_name = serializers.ReadOnlyField(source='patient.last_name')
    class Meta:
        model = Visit
        fields = [
            'id', 'patient', 'patient_name', 'date', 'time',
            'visit_type', 'notify_parent', 'notification_type',
            'comment', 'is_confirmed', 'files', 'created_at',
            'parent_visit_read', 'parent_report_read',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        patient = attrs.get('patient')
        if patient and patient.doctor != request.user:
            raise serializers.ValidationError("You do not have permission to perform this action.")
        return attrs


class TreatmentTypeOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentTypeOption
        fields = ['id', 'code', 'name', 'order']


class CapSystemOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapSystemOption
        fields = ['id', 'code', 'name', 'order']
