# Generated by Django 4.2 on 2023-05-22 08:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsitem",
            name="title",
            field=models.CharField(default="", max_length=255, verbose_name="Title"),
            preserve_default=False,
        ),
    ]
