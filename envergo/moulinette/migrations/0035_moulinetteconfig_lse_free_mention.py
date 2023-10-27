# Generated by Django 4.2 on 2023-10-27 09:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0034_alter_perimeter_is_activated"),
    ]

    operations = [
        migrations.AddField(
            model_name="moulinetteconfig",
            name="lse_free_mention",
            field=models.TextField(
                blank=True,
                verbose_name="LSE > Mention libre «\xa0autres rubriques\xa0»",
            ),
        ),
    ]
