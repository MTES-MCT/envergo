# Generated by Django 4.2 on 2023-10-04 07:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["session_key"], name="analytics_e_session_5d031e_idx"
            ),
        ),
    ]
