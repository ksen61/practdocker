from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documentflow', '0014_email_change_request_attempts'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='replacement',
            name='description',
        ),
    ]
