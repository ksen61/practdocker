from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentflow', '0013_email_change_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailchangerequest',
            name='attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Попытки ввода'),
        ),
        migrations.AddField(
            model_name='emailchangerequest',
            name='resend_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Повторные отправки'),
        ),
        migrations.AddField(
            model_name='emailchangerequest',
            name='last_sent_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Последняя отправка'),
        ),
    ]
