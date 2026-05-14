# notifications/urls.py
from django.urls import path
from .views import FCMTokenView, SendNotificationView

app_name = "notifications"

urlpatterns = [
    # Сохранение / деактивация FCM токена
    path("fcm-token/", FCMTokenView.as_view(), name="fcm-token"),
    # Ручная отправка (admin/staff only)
    path("send/", SendNotificationView.as_view(), name="send"),
]
