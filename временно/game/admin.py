from django.contrib import admin
from .models import (
    CatAvatar, VideoItem, AvatarVideo,
    TaskItem, AvatarTask,
    RewardItem, AvatarReward,
    SettingItem, AvatarSetting
)

class VideoProgressInline(admin.TabularInline):
    model = AvatarVideo
    extra = 0

class TaskProgressInline(admin.TabularInline):
    model = AvatarTask
    extra = 0

class InventoryInline(admin.TabularInline):
    model = AvatarReward
    extra = 0
#админка на аватарки
@admin.register(CatAvatar)
class CatAvatarAdmin(admin.ModelAdmin):
    list_display = ('patient', 'coin_balance', 'xp_balance', 'play_day', 'status')
    search_fields = ('patient__last_name', 'patient__first_name')
    inlines = [VideoProgressInline, TaskProgressInline, InventoryInline]
#админка на видосы
@admin.register(VideoItem)
class VideoItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'unlock_day', 'coin_reward', 'xp_reward', 'status')
    list_editable = ('status', 'unlock_day')
#админка на задания
@admin.register(TaskItem)
class TaskItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient_type', 'unlock_day', 'coin_reward', 'status')
    list_filter = ('patient_type', 'status')
    list_editable = ('status', 'unlock_day')
#админка на награды
@admin.register(RewardItem)
class RewardItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'coin_cost', 'xp_cost', 'is_active')
    list_editable = ('coin_cost', 'xp_cost', 'is_active')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
#админка на настройки(список настроек)
@admin.register(SettingItem)
class SettingItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
#админка на настройки у конкретного пользователя
@admin.register(AvatarSetting)
class AvatarSettingAdmin(admin.ModelAdmin):
    list_display = ('avatar', 'setting_item', 'is_enabled')
    list_filter = ('setting_item', 'is_enabled')