# Generated by Django 3.1.12 on 2021-07-08 14:00

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0002_auto_20210708_1349'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Date created'),
        ),
    ]
