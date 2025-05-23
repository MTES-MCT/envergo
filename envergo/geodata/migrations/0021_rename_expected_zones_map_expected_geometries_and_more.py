# Generated by Django 4.2.19 on 2025-05-13 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geodata", "0020_alter_map_map_type"),
    ]

    operations = [
        migrations.RenameField(
            model_name="map",
            old_name="expected_zones",
            new_name="expected_geometries",
        ),
        migrations.RenameField(
            model_name="map",
            old_name="imported_zones",
            new_name="imported_geometries",
        ),
        migrations.AlterField(
            model_name="map",
            name="expected_geometries",
            field=models.IntegerField(
                default=0, verbose_name="Nb de formes (zones ou lignes) attendues"
            ),
        ),
        migrations.AlterField(
            model_name="map",
            name="imported_geometries",
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name="Nb de formes (zones ou lignes) importées",
            ),
        ),
    ]
