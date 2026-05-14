from rest_framework import serializers
from .models import FCMToken, DeviceType


class FCMTokenSerializer(serializers.ModelSerializer):
    """Сериализатор для сохранения/обновления FCM токена."""

    device_type = serializers.ChoiceField(
        choices=DeviceType.choices, default=DeviceType.UNKNOWN
    )

    class Meta:
        model = FCMToken
        fields = ["token", "device_id", "device_type"]

    def validate_token(self, value):
        if not value or len(value) < 20:
            raise serializers.ValidationError("Невалидный FCM токен.")
        return value


class SendNotificationSerializer(serializers.Serializer):
    """Сериализатор для ручной отправки уведомления через API."""

    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    data = serializers.DictField(child=serializers.CharField(), required=False, default=dict)

    # Кому отправить — либо конкретным пользователям, либо всем
    user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="ID обычных юзеров"
    )
    patient_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="ID пациентов"
    )
    broadcast = serializers.BooleanField(
        default=False, help_text="Отправить всем активным устройствам"
    )


class FCMTokenResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
