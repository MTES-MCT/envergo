# Generated by Django 4.2 on 2024-05-15 08:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0030_remove_request_parcels"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="project_owner_company",
            field=models.CharField(
                blank=True, max_length=128, verbose_name="Project owner company"
            ),
        ),
    ]
