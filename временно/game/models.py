import datetime

from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q, F
from django.utils import timezone
from patients.models import Patient
from datetime import date

class CatAvatar(models.Model):
    patient = models.OneToOneField(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='avatar'
    )
    status = models.BooleanField('QR активирован', default=False)

    coin_balance = models.IntegerField(
        'Баланс игрока',
        default=0,
        validators=[MinValueValidator(0, message='Баланс не может быть отрицательным')]
    )
    xp_balance = models.IntegerField(
        'Опыт игрока',
        default=0,
        validators=[MinValueValidator(0, message='Опыт не может быть отрицательным')]
    )

    play_day = models.IntegerField('Дней в игре', default=1)

    aligner = models.BooleanField('Элайнер',default=False)

    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Аватар пациента'
        verbose_name_plural = 'Аватары пациентов'
        constraints = [
            models.CheckConstraint(
                check=Q(coin_balance__gte=0),
                name = 'coin_balance_not_negative'
            ),
            models.CheckConstraint(
                check=Q(xp_balance__gte=0),
                name = 'xp_balance_not_negative'
            )
        ]

    def __str__(self):
        return f"Cat of {self.patient.full_name}"

    #активируем при заходе
    def activate(self):
        if not self.status:
            self.status = True
            self.activated_at = timezone.now()
            self.save(update_fields=['status', 'activated_at'])

    #возвращает дни игры (в бд хранится такая же инфа, но немного другая логика. День в бд обновляется по скрипту
    #в game/managment/scripts/days_update. Его на серве желательно поставить на автоматический запуск в 00:00.
    #этот вычисляет дату при запросе и упаковывает в тело ответа
    @property
    def current_play_day(self):
        try:
            start_date = self.patient.treatment_start_date
        except AttributeError:
            return 1

        if not start_date:
            return 1

        delta = (date.today() - start_date).days
        return max(1, delta + 1)

class SettingItem(models.Model):
    name = models.CharField("Название настройки", max_length=30, unique=True)
    slug = models.SlugField("Код для фронта", unique=True)

    class Meta:
        verbose_name = "Справочник настроек"
        verbose_name_plural = "Справочник настроек"

    def __str__(self):
        return self.name

class AvatarSetting(models.Model):
    avatar = models.ForeignKey(CatAvatar, on_delete=models.CASCADE, related_name='settings')
    setting_item = models.ForeignKey(SettingItem, on_delete=models.CASCADE)
    is_enabled = models.BooleanField("Переключатель настройки", default=False)

    class Meta:
        unique_together = ('avatar', 'setting_item')
        verbose_name = "Настройка аватара"
        verbose_name_plural = "Настройки аватаров"

class VideoItem(models.Model):
    title = models.CharField('Название видео', max_length=30)
    preview = models.ImageField('Превью видео', upload_to='videos/previews/')
    video = models.FileField('Видео', upload_to='videos/files/')

    coin_reward = models.PositiveIntegerField('Награда(монеты)', default=10)
    xp_reward = models.PositiveIntegerField('Награда(опыт)', default=50)

    status = models.BooleanField('Активно', default=False)
    unlock_day = models.PositiveIntegerField(
        'День открытия',
        default=1,
        help_text = 'День, в который открывается видео'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Видео-урок'
        verbose_name_plural = 'Библиотека видео'

    def __str__(self):
        return f"День {self.unlock_day}: {self.title}"

class AvatarVideo(models.Model):
    avatar = models.ForeignKey(CatAvatar, on_delete=models.CASCADE, related_name='video_progress')
    video = models.ForeignKey(VideoItem, on_delete=models.CASCADE)
    is_completed = models.BooleanField('Статус просмотра', default=False)
    watched_at = models.DateTimeField('Дата просмотра', auto_now=True)

    class Meta:
        unique_together = ('avatar', 'video')
        verbose_name = 'Прогресс видео'
        verbose_name_plural = 'Прогресс видео'

class TaskItem(models.Model):
    CHILD = 'child'
    TEEN = 'teen'
    PATIENT_TYPES = [(CHILD, 'ребенок'), (TEEN, 'подросток')]
    title = models.CharField('Название', max_length=40)
    coin_reward = models.PositiveIntegerField('Награда(монеты)', default=10)
    xp_reward = models.PositiveIntegerField('Награда(опыт)', default=50)

    status = models.BooleanField('Активно', default=False)
    unlock_day = models.PositiveIntegerField(
        'День открытия',
        default=1,
        help_text='День, в который открывается задание'
    )

    patient_type = models.CharField(
        'Тип пациента',
        choices=PATIENT_TYPES,
        default=CHILD
    )

    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Список заданий'

    def __str__(self):
        return f"[{self.get_patient_type_display()}], день {self.unlock_day}: {self.title}"

class AvatarTask(models.Model):
    avatar = models.ForeignKey(CatAvatar, on_delete=models.CASCADE, related_name='task_progress')
    task = models.ForeignKey(TaskItem, on_delete=models.CASCADE)
    is_completed = models.BooleanField('Выполнено', default=False)
    completed_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField('Прочитано в уведомлениях', default=False)

    class Meta:
        unique_together = ('avatar', 'task')
        verbose_name = 'Прогресс задания'
        verbose_name_plural = 'Прогресс заданий'

class RewardItem(models.Model):
    title = models.CharField('Название предмета', max_length=50)
    preview = models.ImageField('Картинка предмета', upload_to='reward/previews/')

    coin_cost = models.PositiveIntegerField('Цена в монетах')
    xp_cost = models.PositiveIntegerField('Цена в опыте')

    is_active = models.BooleanField('Доступно к покупке', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Предмет магазина'
        verbose_name_plural = 'Магазин предметов'

    def __str__(self):
        return f"{self.title} - {self.coin_cost}:coins, {self.xp_cost}:xp; available = {self.is_active}"

class AvatarReward(models.Model):
    avatar = models.ForeignKey(CatAvatar, on_delete=models.CASCADE, related_name='inventory')
    reward = models.ForeignKey(RewardItem, on_delete=models.CASCADE)
    is_equipped = models.BooleanField('Надето', default=False)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('avatar', 'reward')
        verbose_name = 'Инвентарь пациента'
        verbose_name_plural = 'Инвентарь пациентов'


class AvatarSosAlert(models.Model):
    avatar = models.ForeignKey(CatAvatar, on_delete=models.CASCADE, related_name='sos_alerts')
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField('Обработано родителем', default=False)

    class Meta:
        verbose_name = 'SOS-сигнал'
        verbose_name_plural = 'SOS-сигналы'
