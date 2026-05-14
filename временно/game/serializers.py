from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.middleware import get_user
from rest_framework import serializers

from patients.models import Patient, Document, Parent

from .models import CatAvatar, VideoItem, TaskItem, RewardItem, SettingItem, AvatarSosAlert


#api/game/qr-login
class PatientShortInfoInLoginSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    status = serializers.CharField()

#api/game/qr-login
class PatientQRLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    patient = PatientShortInfoInLoginSerializer()

class ParentLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

#api/game/info/parent
class ParentInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = ['last_name', 'first_name', 'middle_name', 'phone', 'email']

#api/game/info/patient
class PatientInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['last_name', 'first_name', 'middle_name', 'birth_date', 'account_type']

#api/game/info/doctor
User = get_user_model()
class DoctorInfoSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    clinic = serializers.CharField(source='clinic_name', read_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'clinic']

    def get_full_name(self, obj):
        return f"{obj.last_name} {obj.first_name} {obj.middle_name}".strip()

#api/game/document
class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['title', 'file']

#api/game/settings
class PatientSettingSerializer(serializers.ModelSerializer):
    setting_id = serializers.IntegerField(source='id')
    is_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = SettingItem
        fields = ['setting_id', 'name', 'is_enabled']

class UpdateSettingSerializer(serializers.Serializer):
    setting_id = serializers.IntegerField()
    enable = serializers.BooleanField()

#api/game/avatar
class PatientAvatarSerializer(serializers.ModelSerializer):
    play_day = serializers.IntegerField(source='current_play_day' ,read_only=True)
    activated_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)

    class Meta:
        model = CatAvatar
        fields = ['status', 'coin_balance', 'xp_balance', 'play_day', 'aligner', 'activated_at']
        read_only_fields = fields

#api/game/avatar/update-aligner
class AlignerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatAvatar
        fields = ['aligner']

#api/game/video
class VideoListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    locked = serializers.SerializerMethodField()

    class Meta:
        model = VideoItem
        fields = [
            'id', 'title', 'preview', 'video',
            'coin_reward', 'xp_reward',
            'unlock_day', 'status', 'locked'
        ]

    def get_locked(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return True
        patient_id = request.user.id
        cat = CatAvatar.objects.filter(patient_id=patient_id).first()
        return cat.play_day < obj.unlock_day

    def get_status(self, obj) -> str:
        is_watched = getattr(obj, 'is_watched_by_user', False)

        if is_watched:
            return "watched"

        if self.get_locked(obj):
            return "locked"

        return "available"

#api/game/task
class TaskListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    locked = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = TaskItem
        fields = [
            'id', 'title', 'coin_reward', 'xp_reward', 'unlock_day',
            'status', 'locked', 'patient_type', 'is_read'
        ]

    def get_locked(self, obj) -> bool:
        request = self.context.get('request')
        patient_id = request.user.id
        cat = CatAvatar.objects.filter(patient_id=patient_id).first()
        return cat.play_day < obj.unlock_day

    def get_status(self, obj) -> str:
        is_completed = getattr(obj, 'is_completed_by_user', False)

        if is_completed:
            return "completed"
        if self.get_locked(obj):
            return "locked"
        return "available"

    def get_is_read(self, obj) -> bool:
        return getattr(obj, 'is_read_by_user', False)

#api/game/shop
class RewardListSerializer(serializers.ModelSerializer):
    is_bought = serializers.BooleanField(read_only=True)
    is_equipped = serializers.BooleanField(read_only=True)

    class Meta:
        model = RewardItem
        fields = [
            'id', 'title', 'preview', 'coin_cost', 'xp_cost',
            'is_active', 'is_bought', 'is_equipped'
        ]


class SosAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarSosAlert
        fields = ['id', 'created_at', 'handled']

#api/game/treatment
class PatientTreatmentProgressSerializer(serializers.ModelSerializer):
    aligner_n = serializers.SerializerMethodField()
    aligner_x = serializers.ReadOnlyField(source='caps_count')
    stage = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['stage', 'change_cycle', 'aligner_n', 'aligner_x']

    def get_stage(self, obj) -> str:
        """
        Этап лечения для отображения родителю:
        - если врач явно указал `treatment_stage` в карточке пациента, используем его
        - иначе берём вычисляемый `current_treatment_stage` (Активное выравнивание / Завершающий этап)
        """
        if getattr(obj, 'treatment_stage', None):
            return obj.treatment_stage
        return getattr(obj, 'current_treatment_stage', '')

    def get_aligner_n(self, obj) -> int:
        if not hasattr(obj, 'treatment_start_date') or not obj.treatment_start_date:
            return 1

        days_passed = (date.today() - obj.treatment_start_date).days
        if days_passed <= 0:
            return 1

        n = (days_passed // obj.change_cycle) + 1
        return min(n, obj.caps_count) if obj.caps_count > 0 else n
