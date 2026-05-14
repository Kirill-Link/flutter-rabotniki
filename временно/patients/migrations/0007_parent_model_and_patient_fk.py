# Generated manually: add Parent model and Patient.parent_id

import django.db.models.deletion
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def create_parents_and_assign(apps, schema_editor):
    Patient = apps.get_model('patients', 'Patient')
    Parent = apps.get_model('patients', 'Parent')
    for p in Patient.objects.all():
        phone = (getattr(p, 'phone', None) or '').strip() or f"migrated_{p.id}"
        parent, _ = Parent.objects.get_or_create(
            phone=phone,
            defaults={
                'first_name': getattr(p, 'parent_first_name', '') or '',
                'last_name': getattr(p, 'parent_last_name', '') or '',
                'middle_name': getattr(p, 'parent_middle_name', '') or '',
                'email': '',
                'password': make_password(''),
            },
        )
        if not parent.password:
            parent.password = make_password('')
            parent.save(update_fields=['password'])
        p.parent = parent
        p.save(update_fields=['parent_id'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0006_visit_parent_report_read_visit_parent_visit_read'),
    ]

    operations = [
        migrations.CreateModel(
            name='Parent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_name', models.CharField(max_length=100, verbose_name='Фамилия')),
                ('first_name', models.CharField(max_length=100, verbose_name='Имя')),
                ('middle_name', models.CharField(blank=True, max_length=100, verbose_name='Отчество')),
                ('phone', models.CharField(max_length=20, unique=True, verbose_name='Телефон (Логин)')),
                ('password', models.CharField(max_length=128, verbose_name='Хеш пароля')),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Родитель',
                'verbose_name_plural': 'Родители',
            },
        ),
        migrations.AddField(
            model_name='patient',
            name='parent',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='children',
                to='patients.parent',
                verbose_name='Родитель',
            ),
        ),
        migrations.RunPython(create_parents_and_assign, noop_reverse),
        migrations.RemoveField(
            model_name='patient',
            name='parent_first_name',
        ),
        migrations.RemoveField(
            model_name='patient',
            name='parent_last_name',
        ),
        migrations.RemoveField(
            model_name='patient',
            name='parent_middle_name',
        ),
        migrations.RemoveField(
            model_name='patient',
            name='phone',
        ),
        migrations.AlterField(
            model_name='patient',
            name='parent',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='children',
                to='patients.parent',
                verbose_name='Родитель',
            ),
        ),
    ]
