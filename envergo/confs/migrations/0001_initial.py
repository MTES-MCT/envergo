# Generated by Django 4.2 on 2023-04-17 13:53

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TopBar",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("message_md", models.TextField(verbose_name="Message")),
                (
                    "message_html",
                    models.TextField(blank=True, verbose_name="Message (html)"),
                ),
                (
                    "is_active",
                    models.BooleanField(default=False, verbose_name="Is active"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Updated at"
                    ),
                ),
            ],
        ),
    ]
