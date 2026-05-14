from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0003_seed_settings'),
        ('game', '0004_rewarditem_settingitem_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='avatartask',
            name='is_read',
            field=models.BooleanField(default=False, verbose_name='Прочитано в уведомлениях'),
        ),
    ]

