from django.core.management.base import BaseCommand
from django.utils import timezone
from game.models import CatAvatar
from django.db.models import F

class Command(BaseCommand):
    help = 'синхронизируем день на основе даты активации(только для БД)'

    def handle(self, *args, **kwargs):
        active_cats = CatAvatar.objects.filter(status=True, activated_at__isnull=False)
        now = timezone.now()
        count = 0

        for cat in active_cats:
            actual_day = (now - cat.activated_at).days + 1

            if actual_day != cat.play_day:
                cat.play_day = actual_day
                cat.save(update_fields=['play_day'])
                count += 1

        self.stdout.write(self.style.SUCCESS(f'Обновлено записей: {count}'))
