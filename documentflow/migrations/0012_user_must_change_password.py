from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentflow', '0011_document_approval_order_document_manual_route'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(default=False, verbose_name='Требуется смена пароля'),
        ),
    ]
