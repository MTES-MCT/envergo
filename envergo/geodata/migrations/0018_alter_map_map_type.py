# Generated by Django 4.2.13 on 2025-01-10 10:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geodata", "0017_zone_attributes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="map",
            name="map_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("zone_humide", "Zone humide"),
                    ("zone_inondable", "Zone inondable"),
                    ("species", "Espèces protégées"),
                ],
                max_length=50,
                verbose_name="Map type",
            ),
        ),
    ]
