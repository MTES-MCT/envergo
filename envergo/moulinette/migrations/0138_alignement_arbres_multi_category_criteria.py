"""Add the "régime unique" and "hors régime unique" L350-3 criteria.

Until now, the L350-3 regulation only carried a criterion for the ``l350_3``
hedge category (plus the Calvados "before régime unique" one, on ``hru``).
The other two categories therefore fell back to "non disponible", although
L350-3 simply does not concern them.

Each existing ``AlignementsArbresL3503`` criterion is duplicated into:

- ``AlignementsArbresHru`` — hors régime unique
- ``AlignementsArbresRu``  — régime unique

Both always return "non concerné". The Calvados criterion is left untouched:
its own result still wins the category cascade for as long as it is valid.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.alignementarbres"

L350_3 = f"{MODULE}.AlignementsArbresL3503"
HRU = f"{MODULE}.AlignementsArbresHru"
RU = f"{MODULE}.AlignementsArbresRu"

HRU_SUFFIX = "Hors régime unique"
RU_SUFFIX = "Régime unique"


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


def add_categories(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    criteria = list(Criterion.objects.filter(evaluator=L350_3))
    logger.info("Migrating alignements d'arbres: %s criteria found", len(criteria))

    for criterion in criteria:
        clone(criterion, HRU, HRU_SUFFIX)
        clone(criterion, RU, RU_SUFFIX)


def remove_categories(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[HRU, RU])
    logger.info("Reverse alignements d'arbres: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0137_change_guh_structure_for_maritime_departments"),
    ]

    operations = [
        migrations.RunPython(add_categories, remove_categories),
    ]
