# Generated by Django 4.2.13 on 2024-10-08 07:45

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0040_requestfile_uploaded_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluation",
            name="urbanism_department_emails",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                blank=True,
                default=list,
                size=None,
                verbose_name="Email service ADS",
            ),
        ),
    ]
