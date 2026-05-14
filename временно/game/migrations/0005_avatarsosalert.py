from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0004_avartartask_is_read'),
    ]

    operations = [
        migrations.CreateModel(
            name='AvatarSosAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('handled', models.BooleanField(default=False, verbose_name='Обработано родителем')),
                ('avatar', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='sos_alerts', to='game.catavatar')),
            ],
            options={
                'verbose_name': 'SOS-сигнал',
                'verbose_name_plural': 'SOS-сигналы',
            },
        ),
    ]

