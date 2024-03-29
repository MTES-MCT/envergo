# Generated by Django 4.2 on 2023-09-21 13:00

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0031_moulinetteconfig_regulations_available"),
    ]

    operations = [
        migrations.AlterField(
            model_name="moulinetteconfig",
            name="regulations_available",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("loi_sur_leau", "Loi sur l'eau"),
                        ("natura2000", "Natura 2000"),
                        ("eval_env", "Évaluation environnementale"),
                        ("sage", "Règlement de SAGE"),
                    ],
                    max_length=64,
                ),
                blank=True,
                default=list,
                size=None,
            ),
        ),
    ]
