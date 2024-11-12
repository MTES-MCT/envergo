# Generated by Django 4.2.13 on 2024-11-08 08:55

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import envergo.evaluations.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("hedges", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PetitionProject",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        db_index=True,
                        default=envergo.evaluations.models.generate_reference,
                        max_length=64,
                        null=True,
                        unique=True,
                        verbose_name="Reference",
                    ),
                ),
                (
                    "moulinette_url",
                    models.URLField(
                        blank=True, max_length=1024, verbose_name="Moulinette url"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Date created"
                    ),
                ),
                (
                    "hedge_data",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="hedges.hedgedata",
                    ),
                ),
            ],
            options={
                "verbose_name": "Petition project",
                "verbose_name_plural": "Petition projects",
            },
        ),
    ]