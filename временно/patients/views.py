import os.path
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Patient, Visit, PatientNote, VisitFile, TreatmentTypeOption, CapSystemOption
from .serializers import (
    PatientUpdateSerializer,
    PatientCreateSerializer,
    VisitSerializer,
    PatientDetailSerializer,
    PatientNoteSerializer,
    TreatmentTypeOptionSerializer,
    CapSystemOptionSerializer,
)

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

FONTS_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')

pdfmetrics.registerFont(TTFont('ClearSans-Regular', os.path.join(FONTS_DIR, 'ClearSans-Regular.ttf')))
pdfmetrics.registerFont(TTFont('ClearSans-Bold', os.path.join(FONTS_DIR, 'ClearSans-Bold.ttf')))

class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Patient.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return PatientCreateSerializer
        if self.action in ['update', 'partial_update']:
            return PatientUpdateSerializer
        return PatientDetailSerializer

    def get_queryset(self):
        # врач видит ТОЛЬКО своих пациентов
        return Patient.objects.filter(doctor=self.request.user)

    def perform_create(self, serializer):
        # автоматически привязываем пациента к текущему врачу
        serializer.save(doctor=self.request.user)

    @action(methods=['post'], detail=True)
    def archive(self, request, pk=None):
        patient = self.get_object()
        patient.status = Patient.STATUS_ARCHIVED
        patient.save()
        return Response({'status': 'patient archived'})

    @action(methods=['post'], detail=True)
    def restore(self, request, pk=None):
        patient = self.get_object()
        patient.status = Patient.STATUS_ACTIVE
        patient.save()
        return Response({'status': 'patient restored'})

    @action(detail=True, methods=['get'])
    def generate_pdf(self, request, pk=None):
        patient = self.get_object()

        password_from_cache = cache.get(f'qr_sheet_pwd_{patient.id}')

        if password_from_cache:
            password_to_print = password_from_cache
        else:
            password_to_print = "Используйте ваш текущий пароль"

        if not hasattr(patient, 'qr_code') or not patient.qr_code.image:
            return Response({"error": "QR не найден"}, status=404)

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        qr_path = patient.qr_code.image.path
        p.drawImage(qr_path, (width - 250) / 2, height - 300, width=250, height=250)

        p.setFont("ClearSans-Bold", 16)
        p.drawCentredString(width / 2, height - 330, f"Пациент: {patient.full_name}")

        p.setFont("ClearSans-Regular", 12)
        p.drawCentredString(width / 2, height - 360, "Данные для входа родителей:")

        p.setFont("ClearSans-Bold", 14)
        p.drawCentredString(width / 2, height - 385, f"Логин (тел): {patient.parent.phone}")

        p.drawCentredString(width / 2, height - 410, f"Пароль: {password_to_print}")

        if password_to_print == "Используйте ваш текущий пароль":
            p.setFont("ClearSans-Regular", 10)

        p.showPage()
        p.save()
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="card_{patient.id}.pdf"'
        return response

class VisitViewSet(viewsets.ModelViewSet):
    serializer_class = VisitSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Visit.objects.all()

    def get_queryset(self):
        # врач видит только свои записи
        base_qs = Visit.objects.filter(doctor=self.request.user)
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            return base_qs.filter(patient_id=patient_id)
        return base_qs

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)

    # те что еще будут
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        queryset = self.get_queryset().filter(date__gte=now().date(), is_confirmed=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # уже завершенные/подтвержденные
    @action(detail=False, methods=['get'])
    def history(self, request):
        queryset = self.get_queryset().filter(is_confirmed=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    #подтверждение явки
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        visit = self.get_object()

        comment = request.data.get('comment')
        visit.is_confirmed = True
        if comment:
            visit.comment = comment

        files = request.FILES.getlist('files')
        created_files = []

        for f in files:
            visit_file = VisitFile.objects.create(file=f, visit=visit)
            created_files.append(visit_file.id)
        visit.save()

        return Response({
            'status': 'visit confirmed',
            'is_confirmed': visit.is_confirmed,
            'comment': visit.comment,
            'uploaded_files_count': len(created_files)
        })


class PatientNoteViewSet(viewsets.ModelViewSet):
    serializer_class = PatientNoteSerializer
    permission_classes = [IsAuthenticated]
    queryset = PatientNote.objects.all()

    def get_queryset(self):
        base_qs = PatientNote.objects.filter(patient__doctor=self.request.user)
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            return base_qs.filter(patient_id=patient_id)
        return base_qs


class TreatmentTypeOptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TreatmentTypeOption.objects.all()
    serializer_class = TreatmentTypeOptionSerializer
    permission_classes = [AllowAny]


class CapSystemOptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CapSystemOption.objects.all()
    serializer_class = CapSystemOptionSerializer
    permission_classes = [AllowAny]
