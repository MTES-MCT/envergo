# Generated by Django 4.2 on 2023-06-27 08:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("geodata", "0003_map_geometry"),
        ("moulinette", "0005_contact_regulation_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="Regulation",
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
                ("title", models.CharField(max_length=256, verbose_name="Title")),
                ("slug", models.SlugField(max_length=256, verbose_name="Slug")),
                (
                    "weight",
                    models.PositiveIntegerField(default=1, verbose_name="Weight"),
                ),
                (
                    "perimeter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="regulations",
                        to="geodata.map",
                        verbose_name="Perimeter",
                    ),
                ),
            ],
            options={
                "verbose_name": "Regulation",
                "verbose_name_plural": "Regulations",
            },
        ),
        migrations.CreateModel(
            name="Criterion",
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
                ("title", models.CharField(max_length=256, verbose_name="Title")),
                ("slug", models.SlugField(max_length=256, verbose_name="Slug")),
                (
                    "subtitle",
                    models.CharField(
                        blank=True, max_length=256, verbose_name="Subtitle"
                    ),
                ),
                (
                    "header",
                    models.CharField(
                        blank=True, max_length=4096, verbose_name="Header"
                    ),
                ),
                (
                    "weight",
                    models.PositiveIntegerField(default=1, verbose_name="Weight"),
                ),
                (
                    "perimeter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="criteria",
                        to="geodata.map",
                        verbose_name="Perimeter",
                    ),
                ),
                (
                    "regulation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="criteria",
                        to="moulinette.regulation",
                        verbose_name="Regulation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Criterion",
                "verbose_name_plural": "Criteria",
            },
        ),
    ]
