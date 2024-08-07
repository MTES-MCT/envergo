# Generated by Django 4.2.13 on 2024-07-22 08:46

from django.db import migrations
import logging

logger = logging.getLogger(__name__)


def set_criteria_perimeters(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    Perimeter = apps.get_model("moulinette", "Perimeter")

    criteria = Criterion.objects.filter(regulation__has_perimeters=True).select_related(
        "activation_map", "regulation"
    )
    logger.info(f"Setting perimeters for {criteria.count()} criteria")
    for criterion in criteria:
        logger.info(f"Setting perimeter for {criterion}")
        perimeters = Perimeter.objects.filter(regulation=criterion.regulation).filter(
            activation_map=criterion.activation_map
        )
        criterion.perimeter = perimeters.first()
        criterion.save()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0056_merge_20240722_1159"),
    ]

    operations = [
        migrations.RunPython(set_criteria_perimeters, migrations.RunPython.noop)
    ]
