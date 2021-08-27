# Generated by Django 3.2.6 on 2021-08-27 08:07

import django.core.validators
from django.db import migrations, models
import envergo.evaluations.models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0014_auto_20210825_0924'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evaluation',
            name='evaluation_file',
            field=models.FileField(blank=True, null=True, upload_to=envergo.evaluations.models.evaluation_file_format, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf'])], verbose_name='Evaluation file'),
        ),
    ]
