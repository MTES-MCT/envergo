# Generated by Django 4.2 on 2023-10-12 09:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0033_perimeter_is_activated"),
    ]

    operations = [
        migrations.AlterField(
            model_name="perimeter",
            name="is_activated",
            field=models.BooleanField(
                default=False,
                help_text="Check if all criteria have been set",
                verbose_name="Is activated",
            ),
        ),
    ]
