# Generated by Django 4.2 on 2023-06-15 07:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("geodata", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="map",
            name="imported_zones",
            field=models.IntegerField(
                blank=True, null=True, verbose_name="Imported zones"
            ),
        ),
    ]
