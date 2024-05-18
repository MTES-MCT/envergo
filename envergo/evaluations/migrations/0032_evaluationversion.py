# Generated by Django 4.2 on 2024-05-18 12:57

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0031_evaluation_project_owner_company"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationVersion",
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
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Date created"
                    ),
                ),
                ("content", models.TextField(verbose_name="Content")),
                (
                    "evaluation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="evaluations.evaluation",
                        verbose_name="Evaluation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evaluation version",
                "verbose_name_plural": "Evaluation versions",
                "ordering": ("-created_at",),
            },
        ),
    ]
