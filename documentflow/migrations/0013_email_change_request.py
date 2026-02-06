from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documentflow', '0012_user_must_change_password'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('new_email', models.EmailField(max_length=254, verbose_name='Новый email')),
                ('code', models.CharField(max_length=6, verbose_name='Код подтверждения')),
                ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='Попытки ввода')),
                ('resend_count', models.PositiveSmallIntegerField(default=0, verbose_name='Повторные отправки')),
                ('last_sent_at', models.DateTimeField(auto_now_add=True, verbose_name='Последняя отправка')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_change_requests', to='documentflow.user', verbose_name='Сотрудник')),
            ],
            options={
                'verbose_name': 'Запрос смены email',
                'verbose_name_plural': 'Запросы смены email',
                'ordering': ['-created_at'],
            },
        ),
    ]
