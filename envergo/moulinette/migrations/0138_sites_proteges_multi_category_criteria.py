"""Split the Sites protégés criteria into per hedge category evaluators.

Until now, a single evaluator carried each Sites protégés criterion (SPR and
MH) for every hedge category. Each evaluator is now tripled, one per category,
with the same result:

- ``…Hru``   — hors régime unique (the historical evaluator, renamed)
- ``…Ru``    — régime unique
- ``…L3503`` — L350-3
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.sites_proteges_haie"

HRU_SUFFIX = "Hors régime unique"
RU_SUFFIX = "Régime unique"
L350_3_SUFFIX = "L350-3"

# (historical evaluator, hru evaluator, ru evaluator, l350-3 evaluator)
SPLITS = [
    (
        f"{MODULE}.SitesPatrimoniauxRemarquablesHaie",
        f"{MODULE}.SitesPatrimoniauxRemarquablesHaieHru",
        f"{MODULE}.SitesPatrimoniauxRemarquablesHaieRu",
        f"{MODULE}.SitesPatrimoniauxRemarquablesHaieL3503",
    ),
    (
        f"{MODULE}.MonumentsHistoriquesHaie",
        f"{MODULE}.MonumentsHistoriquesHaieHru",
        f"{MODULE}.MonumentsHistoriquesHaieRu",
        f"{MODULE}.MonumentsHistoriquesHaieL3503",
    ),
]


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


def split_sites_proteges(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    for old, hru, ru, l350_3 in SPLITS:
        criteria = list(Criterion.objects.filter(evaluator=old))
        logger.info("Migrating %s: %s criteria found", old, len(criteria))

        for criterion in criteria:
            source_title = criterion.backend_title

            # 1. The existing row becomes the "hors régime unique" evaluator.
            criterion.evaluator = hru
            criterion.backend_title = retitle(source_title, HRU_SUFFIX)
            criterion.save()
            logger.info("Update: %s => %s", source_title, criterion.backend_title)

            # 2. The "régime unique" and "L350-3" criteria are new clones.
            clone(criterion, ru, RU_SUFFIX)
            clone(criterion, l350_3, L350_3_SUFFIX)


def merge_sites_proteges(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    for old, hru, ru, l350_3 in SPLITS:
        # The criteria created above have no admin-authored template of their
        # own, but deleting a criterion a template points at is protected, so
        # be explicit.
        obsolete = Criterion.objects.filter(evaluator__in=[ru, l350_3])
        logger.info("Reverse %s: removing %s criteria", old, obsolete.count())
        MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
        obsolete.delete()

        for criterion in Criterion.objects.filter(evaluator=hru):
            source_title = criterion.backend_title
            criterion.evaluator = old
            criterion.backend_title = source_title.rsplit(" - ", 1)[0]
            criterion.save()
            logger.info("Update: %s => %s", source_title, criterion.backend_title)


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0137_change_guh_structure_for_maritime_departments"),
    ]

    operations = [
        migrations.RunPython(split_sites_proteges, merge_sites_proteges),
    ]
