"""Split the EP régime unique criterion into per hedge category evaluators.

Until now, a single ``EspecesProtegeesRegimeUnique`` evaluator carried the EP
régime unique criterion for every hedge category. The evaluators are now one per
category:

- ``EspecesProtegeesRu``    — régime unique (the historical evaluator, renamed)
- ``EspecesProtegeesHru``   — hors régime unique
- ``EspecesProtegeesL3503`` — L350-3

Each existing régime unique criterion is switched to the renamed evaluator, and
gets a sibling criterion for the two other categories.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.ep"

OLD_RU = f"{MODULE}.EspecesProtegeesRegimeUnique"
RU = f"{MODULE}.EspecesProtegeesRu"
HRU = f"{MODULE}.EspecesProtegeesHru"
L350_3 = f"{MODULE}.EspecesProtegeesL3503"

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
    same places as the one it is derived from. The evaluator settings are the
    régime unique ones only, so the clones start without any.
    """
    source_title = criterion.backend_title
    criterion.pk = None
    criterion.evaluator = evaluator
    criterion.evaluator_settings = {}
    criterion.backend_title = retitle(source_title, suffix)
    criterion.save()
    logger.info("Create: %s (from %s)", criterion.backend_title, source_title)
    return criterion


def split_ep_regime_unique(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    criteria = list(Criterion.objects.filter(evaluator=OLD_RU))
    logger.info("Migrating EP régime unique: %s criteria found", len(criteria))

    for criterion in criteria:
        source = Criterion.objects.get(pk=criterion.pk)

        # 1. The existing row keeps the régime unique behaviour under its new name.
        criterion.evaluator = RU
        criterion.save()
        logger.info("Update: %s => %s", OLD_RU, RU)

        # 2. The other categories get their own criterion.
        for evaluator, suffix in ((HRU, HRU_SUFFIX), (L350_3, L350_3_SUFFIX)):
            already_exists = Criterion.objects.filter(
                evaluator=evaluator,
                regulation=source.regulation,
                activation_map=source.activation_map,
                perimeter=source.perimeter,
            ).exists()
            if not already_exists:
                clone(Criterion.objects.get(pk=source.pk), evaluator, suffix)


def merge_ep_regime_unique(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[HRU, L350_3])
    logger.info("Reverse EP régime unique: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()

    updated = Criterion.objects.filter(evaluator=RU).update(evaluator=OLD_RU)
    logger.info("Update: %s criteria back to %s", updated, OLD_RU)


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0141_merge_20260924_1203"),
    ]

    operations = [
        migrations.RunPython(split_ep_regime_unique, merge_ep_regime_unique),
    ]
