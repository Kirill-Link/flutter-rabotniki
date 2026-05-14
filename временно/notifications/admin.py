# notifications/admin.py
from django.contrib import admin
from .models import FCMToken, NotificationLog


@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    list_display = ["short_token", "device_type", "device_id", "is_active", "updated_at", "owner_display"]
    list_filter = ["device_type", "is_active"]
    search_fields = ["token", "device_id"]
    readonly_fields = ["token", "created_at", "updated_at"]

    @admin.display(description="Токен")
    def short_token(self, obj):
        return obj.token[:40] + "..."

    @admin.display(description="Владелец")
    def owner_display(self, obj):
        if obj.owner:
            return f"{obj.content_type} #{obj.object_id} — {obj.owner}"
        return "—"


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "sent_at", "recipient_display"]
    list_filter = ["status", "sent_at"]
    search_fields = ["title", "body"]
    readonly_fields = ["sent_at", "fcm_response"]

    @admin.display(description="Получатель")
    def recipient_display(self, obj):
        if obj.recipient:
            return f"{obj.content_type} #{obj.object_id}"
        return "broadcast"
