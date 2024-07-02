# Generated by Django 4.2.13 on 2024-06-28 09:22

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("geodata", "0015_catchmentareatile_copy_to_staging"),
    ]

    operations = [
        migrations.AlterField(
            model_name="department",
            name="geometry",
            field=django.contrib.gis.db.models.fields.MultiPolygonField(
                null=True, srid=4326
            ),
        ),
    ]