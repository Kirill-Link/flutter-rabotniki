"""
notifications/services.py
Вся логика отправки FCM вынесена сюда — используй из любого модуля:

    from notifications.services import FCMService

    # Отправить одному пациенту
    FCMService.send_to_patient(patient, title="Привет", body="Сообщение")

    # Отправить нескольким юзерам
    FCMService.send_to_users([user1, user2], title="...", body="...")

    # Broadcast
    FCMService.send_broadcast(title="...", body="...")
"""

import logging
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from .models import FCMToken, NotificationLog

logger = logging.getLogger(__name__)


def _get_firebase_app():
    """Lazy инициализация Firebase Admin SDK."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


class FCMService:
    """
    Сервис отправки Firebase Cloud Messaging уведомлений.
    Все методы — classmethod, инстанс не нужен.
    """

    @classmethod
    def _send_messages(
        cls,
        tokens: list[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
        recipient=None,
    ) -> dict:
        """
        Низкоуровневая отправка по списку токенов.
        Возвращает dict с результатом.
        """
        if not tokens:
            logger.warning("FCMService: пустой список токенов, отправка пропущена.")
            return {"success": 0, "failure": 0, "responses": []}

        _get_firebase_app()

        # Нормализуем data — FCM принимает только строки
        str_data = {k: str(v) for k, v in (data or {}).items()}

        messages = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                token=token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        priority="high",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1)
                    )
                ),
            )
            for token in tokens
        ]

        batch_response = messaging.send_each(messages)

        success_count = batch_response.success_count
        failure_count = batch_response.failure_count
        responses = []

        invalid_tokens = []
        for token, resp in zip(tokens, batch_response.responses):
            entry = {"token": token[:20] + "...", "success": resp.success}
            if not resp.success:
                entry["error"] = str(resp.exception)
                # Деактивируем невалидные токены
                if resp.exception and hasattr(resp.exception, "code"):
                    if resp.exception.code in (
                        "registration-token-not-registered",
                        "invalid-registration-token",
                    ):
                        invalid_tokens.append(token)
            responses.append(entry)

        if invalid_tokens:
            FCMToken.objects.filter(token__in=invalid_tokens).update(is_active=False)
            logger.info(f"FCMService: деактивировано {len(invalid_tokens)} токенов.")

        result = {
            "success": success_count,
            "failure": failure_count,
            "responses": responses,
        }

        # Логируем в БД
        status = (
            NotificationLog.Status.SUCCESS
            if failure_count == 0
            else (
                NotificationLog.Status.PARTIAL
                if success_count > 0
                else NotificationLog.Status.FAILED
            )
        )
        ct = (
            ContentType.objects.get_for_model(recipient)
            if recipient
            else None
        )
        NotificationLog.objects.create(
            title=title,
            body=body,
            data=str_data,
            content_type=ct,
            object_id=recipient.pk if recipient else None,
            status=status,
            fcm_response=result,
        )

        return result

    @classmethod
    def _get_tokens_for(cls, owner) -> list[str]:
        """Получить активные токены для любого объекта (User или Patient)."""
        ct = ContentType.objects.get_for_model(owner)
        return list(
            FCMToken.objects.filter(
                content_type=ct, object_id=owner.pk, is_active=True
            ).values_list("token", flat=True)
        )

    # ------------------------------------------------------------------ #
    #  Публичный API                                                       #
    # ------------------------------------------------------------------ #

    @classmethod
    def send_to_user(cls, user, title: str, body: str, data: Optional[dict] = None):
        """Отправить уведомление одному User (врач/менеджер)."""
        tokens = cls._get_tokens_for(user)
        return cls._send_messages(tokens, title, body, data, recipient=user)

    @classmethod
    def send_to_users(cls, users, title: str, body: str, data: Optional[dict] = None):
        """Отправить нескольким User."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        user_ids = [u.pk for u in users]
        tokens = list(
            FCMToken.objects.filter(
                content_type=ct, object_id__in=user_ids, is_active=True
            ).values_list("token", flat=True)
        )
        return cls._send_messages(tokens, title, body, data)

    @classmethod
    def send_to_patient(cls, patient, title: str, body: str, data: Optional[dict] = None):
        """Отправить уведомление одному Patient."""
        tokens = cls._get_tokens_for(patient)
        return cls._send_messages(tokens, title, body, data, recipient=patient)

    @classmethod
    def send_to_patients(cls, patients, title: str, body: str, data: Optional[dict] = None):
        """Отправить нескольким Patient."""
        # Импортируем здесь чтобы избежать circular import
        from django.apps import apps
        Patient = apps.get_model("patients", "Patient")  # <-- поменяй на свой app_label
        ct = ContentType.objects.get_for_model(Patient)
        patient_ids = [p.pk for p in patients]
        tokens = list(
            FCMToken.objects.filter(
                content_type=ct, object_id__in=patient_ids, is_active=True
            ).values_list("token", flat=True)
        )
        return cls._send_messages(tokens, title, body, data)

    @classmethod
    def send_broadcast(cls, title: str, body: str, data: Optional[dict] = None):
        """Отправить всем активным устройствам."""
        tokens = list(
            FCMToken.objects.filter(is_active=True).values_list("token", flat=True)
        )
        return cls._send_messages(tokens, title, body, data)

    @classmethod
    def send_to_patient_by_id(cls, patient_id: int, title: str, body: str, data: Optional[dict] = None):
        """Удобный метод — отправить по ID пациента без подгрузки объекта."""
        from django.apps import apps
        Patient = apps.get_model("patients", "Patient")  # <-- поменяй на свой app_label
        ct = ContentType.objects.get_for_model(Patient)
        tokens = list(
            FCMToken.objects.filter(
                content_type=ct, object_id=patient_id, is_active=True
            ).values_list("token", flat=True)
        )
        return cls._send_messages(tokens, title, body, data)
