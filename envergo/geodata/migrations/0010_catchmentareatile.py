# Generated by Django 4.2 on 2024-02-20 09:08

import django.contrib.gis.db.models.fields
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("geodata", "0009_alter_map_import_date"),
    ]

    operations = [
        CreateExtension("postgis_raster"),
        migrations.CreateModel(
            name="CatchmentAreaTile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "data",
                    django.contrib.gis.db.models.fields.RasterField(
                        srid=4326, verbose_name="Data"
                    ),
                ),
            ],
            options={
                "verbose_name": "Catchment area tile",
                "verbose_name_plural": "Catchment area tiles",
            },
        ),
    ]
