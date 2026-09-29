"""Add régime unique haie criteria for the HRU and L350-3 categories.

Until now, régime unique haie only had a single evaluator
(``RegimeUniqueHaieRu``), covering hedges under the régime unique. Hedges
outside the régime unique (HRU) and roadside tree alignments (L350-3) are
never covered by this procedure, so two new evaluators are added, always
returning "non_concerne":

- ``RegimeUniqueHaieHru``   — hors régime unique
- ``RegimeUniqueHaieL3503`` — L350-3
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.regime_unique_haie"

RU = f"{MODULE}.RegimeUniqueHaieRu"
HRU = f"{MODULE}.RegimeUniqueHaieHru"
L350_3 = f"{MODULE}.RegimeUniqueHaieL3503"

HRU_SUFFIX = "Hors régime unique"
L350_3_SUFFIX = "L350-3"


def retitle(backend_title, suffix):
    """Replace the trailing " - <category>" marker of a criterion title."""
    base = backend_title.rsplit(" - ", 1)[0]
    return f"{base} - {suffix}"


def clone(criterion, evaluator, suffix):
    """Duplicate a criterion under another evaluator.

    Copies every field of the source row (activation map, mode and distance,
    perimeter, weight, wording…) so the new criterion activates in exactly the
    same places as the one it is derived from.
    """
    source_title = criterion.backend_title
    criterion.pk = None
    criterion.evaluator = evaluator
    criterion.backend_title = retitle(source_title, suffix)
    criterion.save()
    logger.info("Create: %s (from %s)", criterion.backend_title, source_title)
    return criterion


def create_hru_and_l350_3(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    criteria = list(Criterion.objects.filter(evaluator=RU))
    logger.info("Migrating Régime unique haie: %s criteria found", len(criteria))

    for criterion in criteria:
        clone(criterion, HRU, HRU_SUFFIX)
        clone(criterion, L350_3, L350_3_SUFFIX)


def reverse(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    obsolete = Criterion.objects.filter(evaluator__in=[HRU, L350_3])
    logger.info("Reverse Régime unique haie: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0137_change_guh_structure_for_maritime_departments"),
    ]

    operations = [
        migrations.RunPython(create_hru_and_l350_3, reverse),
    ]
