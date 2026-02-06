from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentflow', '0015_remove_replacement_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='replacement',
            name='end_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата окончания'),
        ),
    ]
