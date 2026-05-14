# Remove obsolete email column from Patient (email is on Parent only)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0007_parent_model_and_patient_fk'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='patient',
            name='email',
        ),
    ]
