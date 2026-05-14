import uuid
import qrcode
from io import BytesIO
from email.policy import default
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class TreatmentTypeOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Тип лечения'
        verbose_name_plural = 'Типы лечения'

    def __str__(self):
        return self.name


class CapSystemOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Система капп'
        verbose_name_plural = 'Системы капп'

    def __str__(self):
        return self.name


class Parent(models.Model):
    # личные данные
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    middle_name = models.CharField("Отчество", max_length=100, blank=True)

    # авторизация
    phone = models.CharField("Телефон (Логин)", max_length=20, unique=True)
    password = models.CharField("Хеш пароля", max_length=128)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Родитель"
        verbose_name_plural = "Родители"

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.phone})"

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class Patient(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    # новые связи
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patients',
        verbose_name="Врач"
    )

    parent = models.ForeignKey(
        Parent,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name="Родитель"
    )

    # личные данные ребенка
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField()
    patient_photo = models.ImageField(
        "Фото пациента",
        upload_to='patients/patients_photos/',
        blank=True,
        null=True,
    )

    # данные лечения
    treatment_type = models.CharField(max_length=50)
    cap_system = models.CharField(max_length=50)
    treatment_stage = models.CharField("Этап лечения", max_length=100, blank=True)
    caps_count = models.PositiveIntegerField(default=0)
    change_cycle = models.PositiveIntegerField(default=7)
    treatment_start_date = models.DateField("Дата начала ношения первой каппы", null=True, blank=True)
    account_type = models.CharField(max_length=10, default='teen')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()

    @property
    def current_aligner_number(self) -> int:
        if not self.treatment_start_date:
            return 1

        days_passed = (date.today() - self.treatment_start_date).days
        if days_passed < 0:
            return 1

        n = (days_passed // self.change_cycle) + 1

        return min(n, self.caps_count) if self.caps_count > 0 else n

    @property
    def current_treatment_stage(self) -> str:
        if self.current_aligner_number >= self.caps_count and self.caps_count > 0:
            return "Завершающий этап"
        return "Активное выравнивание"

#отдельная таблица для кодов
class PatientQR(models.Model):
    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='qr_code',
    )
    image = models.ImageField(
        "Binary code of image",
        upload_to = 'patients/qrcodes/',
        blank=True,
        null=True
    )
    content_url = models.URLField("URL in image")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_qr'
        verbose_name = "Patient's QR-Code"

#создание qr-кода сразу при создании пациента
@receiver(post_save, sender=Patient)
def generate_qr_for_new_patient(sender, instance, created, **kwargs):
    if created:
        qr_url = f"https://app-magic-smile.lp-agency.com/login/{instance.external_id}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')

        qr_obj = PatientQR.objects.create(
            patient=instance,
            content_url=qr_url,
        )
        file_name = f"qr_{instance.external_id}.png"
        qr_obj.image.save(file_name, buffer)


class Visit(models.Model):
    VISIT_TYPE_CHOICES = [
        ('planned', 'Плановый'),
        ('emergency', 'Срочный'),
    ]

    NOTIFICATION_TYPE_CHOICES = [
        ('important', 'Важно'),
        ('regular', 'Обычное'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visits')
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # из модалки назначения
    date = models.DateField("Дата")
    time = models.TimeField("Время")
    visit_type = models.CharField("Тип визита", max_length=20, choices=VISIT_TYPE_CHOICES, default='planned')
    notify_parent = models.BooleanField("Уведомить родителя", default=False)
    notification_type = models.CharField("Тип уведомления", max_length=20, choices=NOTIFICATION_TYPE_CHOICES,
                                         default='regular')

    # модалки подтверждения
    comment = models.TextField("Комментарий врача", blank=True)
    is_confirmed = models.BooleanField("Явка подтверждена", default=False)

    parent_visit_read = models.BooleanField(
        "Уведомление о визите прочитано родителем",
        default=False,
    )
    parent_report_read = models.BooleanField(
        "Отчёт по визиту прочитан родителем",
        default=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-time']


class VisitFile(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='visits/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class PatientNote(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='notes')
    text = models.TextField("Примечания пациента")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Document(models.Model):
    title = models.CharField('Название файла', max_length=30)
    file = models.FileField(upload_to='documents/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'

    def __str__(self):
        return self.title
