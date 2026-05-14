from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import FCMToken
from .serializers import FCMTokenSerializer, SendNotificationSerializer
from .services import FCMService


# ---------------------------------------------------------------------------
# Вспомогательная функция: определяем владельца из request
# ---------------------------------------------------------------------------

def _get_owner_from_request(request):
    """
    Возвращает (owner_object, content_type) для текущего запроса.
    Поддерживает три схемы авторизации из твоего API:
      - jwtAuth       → request.user  (врач / менеджер)
      - PatientAuth   → request.patient  (если у тебя есть такой атрибут)
      - ParentAuth    → request.parent
    Возвращает None, None если не удалось определить.
    """
    # Попытка 1: стандартный JWT-юзер (врач/менеджер)
    if hasattr(request, "user") and request.user and getattr(request.user, "is_authenticated", False):
        user = request.user
        
        # Если это кастомные AuthPatient или AuthParent
        role = getattr(user, "role", None)
        if role in ["patient", "parent"]:
            from django.apps import apps
            Patient = apps.get_model("patients", "Patient")
            try:
                patient_obj = Patient.objects.get(id=user.id)
                ct = ContentType.objects.get_for_model(Patient)
                return patient_obj, ct
            except Patient.DoesNotExist:
                return None, None
                
        # Иначе это обычный юзер (врач)
        ct = ContentType.objects.get_for_model(user)
        return user, ct

    return None, None


# ---------------------------------------------------------------------------
# POST /api/notifications/fcm-token/
# Сохранение / обновление FCM токена текущего пользователя
# ---------------------------------------------------------------------------

from game.authentication import PatientJWTAuthentication, ParentJWTAuthentication

class FCMTokenView(APIView):
    """
    Регистрация FCM токена устройства.
    Привязывается к аутентифицированному пользователю (User или Patient).

    POST body:
        {
            "token": "...",
            "device_id": "abc123",
            "device_type": "android"  // android | apple | web | unknown
        }
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication, PatientJWTAuthentication, ParentJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FCMTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        owner, ct = _get_owner_from_request(request)
        if owner is None:
            return Response(
                {"detail": "Аутентификация не удалась или тип пользователя не поддерживается."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token_value = serializer.validated_data["token"]
        device_id = serializer.validated_data.get("device_id", "")
        device_type = serializer.validated_data.get("device_type", "unknown")

        # Upsert: если токен уже существует — обновляем владельца и метаданные
        fcm_token, created = FCMToken.objects.update_or_create(
            token=token_value,
            defaults={
                "content_type": ct,
                "object_id": owner.pk,
                "device_id": device_id,
                "device_type": device_type,
                "is_active": True,
            },
        )

        return Response(
            {
                "status": "ok",
                "message": "Токен сохранён." if created else "Токен обновлён.",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        """Деактивация токена при logout."""
        token_value = request.data.get("token")
        if not token_value:
            return Response(
                {"detail": "Поле token обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        FCMToken.objects.filter(token=token_value).update(is_active=False)
        return Response({"status": "ok", "message": "Токен деактивирован."})


# ---------------------------------------------------------------------------
# POST /api/notifications/send/
# Ручная отправка (только для staff / врачей)
# ---------------------------------------------------------------------------

class SendNotificationView(APIView):
    """
    Ручная отправка уведомлений.
    Доступ: только is_staff (врачи / администраторы).

    POST body (примеры):

    1) Всем:
        {"title": "...", "body": "...", "broadcast": true}

    2) Конкретным пациентам:
        {"title": "...", "body": "...", "patient_ids": [1, 2, 3]}

    3) Конкретным юзерам:
        {"title": "...", "body": "...", "user_ids": [10, 11]}
    """

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated, IsAdminUser
        return [IsAuthenticated(), IsAdminUser()]

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        title = data["title"]
        body = data["body"]
        extra_data = data.get("data", {})

        if data.get("broadcast"):
            result = FCMService.send_broadcast(title, body, extra_data)

        elif data.get("patient_ids"):
            from django.apps import apps
            Patient = apps.get_model("patients", "Patient")  # поменяй на свой app
            ct = ContentType.objects.get_for_model(Patient)
            tokens = list(
                FCMToken.objects.filter(
                    content_type=ct,
                    object_id__in=data["patient_ids"],
                    is_active=True,
                ).values_list("token", flat=True)
            )
            result = FCMService._send_messages(tokens, title, body, extra_data)

        elif data.get("user_ids"):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            ct = ContentType.objects.get_for_model(User)
            tokens = list(
                FCMToken.objects.filter(
                    content_type=ct,
                    object_id__in=data["user_ids"],
                    is_active=True,
                ).values_list("token", flat=True)
            )
            result = FCMService._send_messages(tokens, title, body, extra_data)

        else:
            return Response(
                {"detail": "Укажи broadcast=true, patient_ids или user_ids."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_200_OK)
