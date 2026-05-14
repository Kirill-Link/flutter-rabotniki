from django.db import migrations


def seed_rewards(apps, schema_editor):
  RewardItem = apps.get_model('game', 'RewardItem')

  items = [
    {"title": "Очки", "coin_cost": 20, "xp_cost": 0},
    {"title": "Кепка", "coin_cost": 50, "xp_cost": 0},
    {"title": "Корона", "coin_cost": 100, "xp_cost": 0},
    {"title": "Наушники", "coin_cost": 75, "xp_cost": 0},
    {"title": "Квадратные очки", "coin_cost": 30, "xp_cost": 0},
    {"title": "Солнцезащитные очки", "coin_cost": 40, "xp_cost": 0},
    {"title": "Шляпа стоматолога", "coin_cost": 150, "xp_cost": 0},
    {"title": "Щит", "coin_cost": 0, "xp_cost": 500},
    {"title": "Плащ", "coin_cost": 0, "xp_cost": 300},
  ]

  for item in items:
    RewardItem.objects.update_or_create(
      title=item["title"],
      defaults={
        "coin_cost": item["coin_cost"],
        "xp_cost": item["xp_cost"],
        "is_active": True,
      },
    )


def unseed_rewards(apps, schema_editor):
  RewardItem = apps.get_model('game', 'RewardItem')
  titles = ["Очки", "Кепка", "Корона", "Наушники", "Квадратные очки", "Солнцезащитные очки", "Шляпа стоматолога", "Щит", "Плащ"]
  RewardItem.objects.filter(title__in=titles).update(is_active=False)


class Migration(migrations.Migration):

  dependencies = [
    ('game', '0001_initial'),
  ]

  operations = [
    migrations.RunPython(seed_rewards, reverse_code=unseed_rewards),
  ]

