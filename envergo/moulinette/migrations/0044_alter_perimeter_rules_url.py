# Generated by Django 4.2 on 2023-12-11 14:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0043_merge_20231208_1416"),
    ]

    operations = [
        migrations.AlterField(
            model_name="perimeter",
            name="rules_url",
            field=models.URLField(blank=True, verbose_name="Rules url"),
        ),
    ]
