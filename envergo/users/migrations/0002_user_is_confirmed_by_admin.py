# Generated by Django 4.2.13 on 2024-12-10 14:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_confirmed_by_admin",
            field=models.BooleanField(
                default=True, verbose_name="Confirmed by an admin"
            ),
        ),
    ]
