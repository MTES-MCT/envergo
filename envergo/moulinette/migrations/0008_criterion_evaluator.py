# Generated by Django 4.2 on 2023-06-28 10:05

from django.db import migrations
import envergo.moulinette.fields


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0007_criterion_activation_distance_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="criterion",
            name="evaluator",
            field=envergo.moulinette.fields.CriterionEvaluatorChoiceField(
                choices=[], default="", verbose_name="Evaluator"
            ),
            preserve_default=False,
        ),
    ]
