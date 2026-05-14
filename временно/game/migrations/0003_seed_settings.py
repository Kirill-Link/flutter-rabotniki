from django.db import migrations


def seed_settings(apps, schema_editor):
  SettingItem = apps.get_model('game', 'SettingItem')

  items = [
    {"name": "Уведомления", "slug": "notifications"},
    {"name": "Музыка", "slug": "music"},
    {"name": "Звук уведомлений", "slug": "notification_sound"},
  ]

  for item in items:
    SettingItem.objects.update_or_create(
      slug=item["slug"],
      defaults={"name": item["name"]},
    )


def unseed_settings(apps, schema_editor):
  SettingItem = apps.get_model('game', 'SettingItem')
  slugs = ["notifications", "music", "notification_sound"]
  SettingItem.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

  dependencies = [
    ('game', '0002_seed_reward_items'),
  ]

  operations = [
    migrations.RunPython(seed_settings, reverse_code=unseed_settings),
  ]

