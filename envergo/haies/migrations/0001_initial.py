# Generated by Django 4.2.13 on 2024-09-25 13:11

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HedgeData",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("data", models.JSONField()),
            ],
            options={
                "verbose_name": "Hedge data",
                "verbose_name_plural": "Hedge data",
            },
        ),
    ]
