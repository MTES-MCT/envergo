# Generated by Django 4.2.13 on 2024-10-08 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0041_alter_evaluation_urbanism_department_emails"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluationversion",
            name="published",
            field=models.BooleanField(default=True, verbose_name="Is published?"),
        ),
        migrations.AddConstraint(
            model_name="evaluationversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("published", True)),
                fields=("evaluation",),
                name="unique_published_version",
            ),
        ),
    ]