"""Split the Réserves naturelles criterion into per hedge category evaluators.

Until now, a single evaluator (``ReservesNaturelles``) carried the Réserves
naturelles criterion for every hedge category, even though it only ever meant
to cover hedges under the régime unique. The evaluator is now tripled, one
per category, and the historical evaluator becomes the "régime unique" one:

- ``ReservesNaturellesRu``   — régime unique (the historical evaluator, renamed)
- ``ReservesNaturellesHru``  — hors régime unique
- ``ReservesNaturellesL3503``— L350-3

Also fixes the Regulation row itself, which was left on the generic
``HaieRegulationEvaluator`` instead of ``ReservesNaturellesRegulation``.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.reserves_naturelles"

OLD = f"{MODULE}.ReservesNaturelles"
RU = f"{MODULE}.ReservesNaturellesRu"
HRU = f"{MODULE}.ReservesNaturellesHru"
L350_3 = f"{MODULE}.ReservesNaturellesL3503"

RU_SUFFIX = "Régime unique"
HRU_SUFFIX = "Hors régime unique"
L350_3_SUFFIX = "L350-3"

# The régime-unique-aware ReservesNaturellesRegulation evaluator (choice_label,
# PROCEDURE_TYPE_MATRIX, instructor-view context) was defined but never wired
# up on the Regulation row itself, which was left on the generic
# HaieRegulationEvaluator base class.
REGULATION_BASE = "envergo.moulinette.regulations.HaieRegulationEvaluator"
REGULATION_EVALUATOR = f"{MODULE}.ReservesNaturellesRegulation"


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


def split_reserves_naturelles(apps, schema_editor):
    Regulation = apps.get_model("moulinette", "Regulation")
    Criterion = apps.get_model("moulinette", "Criterion")

    fixed = Regulation.objects.filter(
        regulation="reserves_naturelles", evaluator=REGULATION_BASE
    ).update(evaluator=REGULATION_EVALUATOR)
    logger.info("Regulation evaluator fixed for %s reserves_naturelles row(s)", fixed)

    criteria = list(Criterion.objects.filter(evaluator=OLD))
    logger.info("Migrating Réserves naturelles: %s criteria found", len(criteria))

    for criterion in criteria:
        source_title = criterion.backend_title

        # 1. The existing row becomes the "régime unique" evaluator.
        criterion.evaluator = RU
        criterion.backend_title = retitle(source_title, RU_SUFFIX)
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)

        # 2. The "hors régime unique" and "L350-3" criteria are new clones.
        clone(criterion, HRU, HRU_SUFFIX)
        clone(criterion, L350_3, L350_3_SUFFIX)


def merge_reserves_naturelles(apps, schema_editor):
    Regulation = apps.get_model("moulinette", "Regulation")
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    Regulation.objects.filter(
        regulation="reserves_naturelles", evaluator=REGULATION_EVALUATOR
    ).update(evaluator=REGULATION_BASE)

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[HRU, L350_3])
    logger.info("Reverse Réserves naturelles: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()

    for criterion in Criterion.objects.filter(evaluator=RU):
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
        migrations.RunPython(split_reserves_naturelles, merge_reserves_naturelles),
    ]
