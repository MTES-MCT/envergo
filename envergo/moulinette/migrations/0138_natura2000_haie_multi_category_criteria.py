"""Split the Natura 2000 haie criterion into per hedge category evaluators.

Until now, a single evaluator (``Natura2000Haie``) carried the Natura 2000
criterion for every hedge category. It is now tripled, one per category:

- ``Natura2000HaieHru``  — hors régime unique (the historical evaluator, renamed)
- ``Natura2000HaieRu``   — régime unique
- ``Natura2000HaieL3503``— L350-3

The configuration is copied as-is, except for the "régime unique" criteria:
hedges under the régime unique are never tree alignments, so their evaluator
has no ``concerne_aa`` setting.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.natura2000_haie"

OLD = f"{MODULE}.Natura2000Haie"
HRU = f"{MODULE}.Natura2000HaieHru"
RU = f"{MODULE}.Natura2000HaieRu"
L350_3 = f"{MODULE}.Natura2000HaieL3503"

HRU_SUFFIX = "Hors régime unique"
RU_SUFFIX = "Régime unique"
L350_3_SUFFIX = "L350-3"


def clone(criterion, source_title, evaluator, suffix, settings):
    """Duplicate a criterion under another evaluator.

    Copies every field of the source row (activation map, mode and distance,
    perimeter, weight, wording…) so the new criterion activates in exactly the
    same places as the one it is derived from.
    """
    criterion.pk = None
    criterion.evaluator = evaluator
    criterion.backend_title = f"{source_title} - {suffix}"
    criterion.evaluator_settings = settings
    criterion.save()
    logger.info("Create: %s (from %s)", criterion.backend_title, source_title)


def split_natura2000_haie(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    criteria = list(Criterion.objects.filter(evaluator=OLD))
    logger.info("Migrating Natura 2000 haie: %s criteria found", len(criteria))

    for criterion in criteria:
        source_title = criterion.backend_title
        # Cloning mutates the instance in place, so keep the source values around.
        source_settings = dict(criterion.evaluator_settings or {})

        # 1. The existing row becomes the "hors régime unique" evaluator.
        criterion.evaluator = HRU
        criterion.backend_title = f"{source_title} - {HRU_SUFFIX}"
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)

        # 2. "L350-3" keeps the very same settings as "hors régime unique".
        clone(criterion, source_title, L350_3, L350_3_SUFFIX, source_settings)

        # 3. "Régime unique" hedges are never tree alignments: drop `concerne_aa`.
        ru_settings = {
            key: value for key, value in source_settings.items() if key != "concerne_aa"
        }
        clone(criterion, source_title, RU, RU_SUFFIX, ru_settings)


def merge_natura2000_haie(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[RU, L350_3])
    logger.info("Reverse Natura 2000 haie: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()

    for criterion in Criterion.objects.filter(evaluator=HRU):
        source_title = criterion.backend_title
        criterion.evaluator = OLD
        criterion.backend_title = source_title.rsplit(" - ", 1)[0]
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0137_change_guh_structure_for_maritime_departments"),
    ]

    operations = [
        migrations.RunPython(split_natura2000_haie, merge_natura2000_haie),
    ]
