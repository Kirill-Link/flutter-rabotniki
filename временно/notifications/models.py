from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class DeviceType(models.TextChoices):
    ANDROID = "android", "Android"
    IOS = "apple", "iOS (Apple)"
    WEB = "web", "Web"
    UNKNOWN = "unknown", "Unknown"


class FCMToken(models.Model):
    """
    FCM-токен устройства.
    Привязывается либо к обычному User (JWT / врач),
    либо к Patient (PatientAuth) через GenericForeignKey.
    """

    # --- владелец (User ИЛИ Patient) ---
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Тип владельца",
    )
    object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID владельца"
    )
    owner = GenericForeignKey("content_type", "object_id")

    # --- поля токена ---
    token = models.TextField(unique=True, verbose_name="FCM токен")
    device_id = models.CharField(
        max_length=255, blank=True, verbose_name="ID устройства"
    )
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
        verbose_name="Тип устройства",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FCM токен"
        verbose_name_plural = "FCM токены"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["token"]),
        ]

    def __str__(self):
        return f"{self.device_type} | {self.token[:30]}..."


class NotificationLog(models.Model):
    """Лог отправленных уведомлений (опционально, удобно для дебага)."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"
        PARTIAL = "partial", "Частично"

    title = models.CharField(max_length=255, verbose_name="Заголовок")
    body = models.TextField(verbose_name="Текст")
    data = models.JSONField(default=dict, blank=True, verbose_name="Доп. данные")

    # Кому отправляли (необязательно — может быть broadcast)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    recipient = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUCCESS
    )
    fcm_response = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лог уведомления"
        verbose_name_plural = "Лог уведомлений"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"[{self.status}] {self.title} — {self.sent_at:%Y-%m-%d %H:%M}"
