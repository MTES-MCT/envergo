"""Split the BCAE8 criterion into a "before régime unique" one and per-category ones.

Until now, a single evaluator carried the whole BCAE8 decision tree, declined
in two criteria by migration 0129: ``Bcae8Hru`` (hors régime unique) and
``Bcae8Ru`` (régime unique).

So the evaluators are now:

- ``Bcae8BeforeRu``  — the historical decision tree, valid until RU_START_DATE
- ``Bcae8Ru``        — "soumis" as soon as a PAC plot is touched
- ``Bcae8Hru``       — "non concerné"
- ``Bcae8L3503``     — "non concerné"

``Bcae8Hru`` keeps its name but changes meaning, so the existing rows carrying
the decision tree are switched to ``Bcae8BeforeRu`` *before* the new
``Bcae8Hru`` rows are created.
"""

import logging
from datetime import date

from django.db import migrations
from psycopg.types.range import DateRange

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.conditionnalitepac"

BEFORE_RU = f"{MODULE}.Bcae8BeforeRu"
HRU = f"{MODULE}.Bcae8Hru"
RU = f"{MODULE}.Bcae8Ru"
L350_3 = f"{MODULE}.Bcae8L3503"

# Date the régime unique takes effect, as already used for the alignements
# d'arbres criteria in migration 0129.
RU_START_DATE = date(2026, 10, 1)

BEFORE_RU_SUFFIX = "Avant régime unique"
HRU_SUFFIX = "Hors régime unique"
RU_SUFFIX = "Régime unique"
L350_3_SUFFIX = "L350-3"

# Criterion templates are looked up as
# "moulinette/{regulation}/{category}/{base_slug}_{result_code}.html", and the
# base slug of the decision tree evaluator went from "bcae8" to
# "bcae8_before_ru". Admin-authored overrides are stored in
# MoulinetteTemplate.key using that same path, so they have to follow.
OLD_TEMPLATE_PREFIX = "conditionnalite_pac/hru/bcae8_"
NEW_TEMPLATE_PREFIX = "conditionnalite_pac/hru/bcae8_before_ru_"
# The only "bcae8_" template of the hru category that does NOT belong to the
# decision tree: it is the new stub evaluator's own template.
KEPT_TEMPLATE_KEY = "conditionnalite_pac/hru/bcae8_non_concerne.html"


def retitle(backend_title, suffix):
    """Replace the trailing " - <category>" marker of a criterion title."""
    base = backend_title.rsplit(" - ", 1)[0]
    return f"{base} - {suffix}"


def clone(criterion, evaluator, suffix, validity_range):
    """Duplicate a criterion under another evaluator.

    Copies every field of the source row (activation map, mode and distance,
    perimeter, weight, wording…) so the new criterion activates in exactly the
    same places as the one it is derived from.
    """
    source_title = criterion.backend_title
    criterion.pk = None
    criterion.evaluator = evaluator
    criterion.backend_title = retitle(source_title, suffix)
    criterion.validity_range = validity_range
    criterion.save()
    logger.info("Create: %s (from %s)", criterion.backend_title, source_title)
    return criterion


def split_bcae8(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    decision_tree_criteria = list(Criterion.objects.filter(evaluator=HRU))
    logger.info("Migrating BCAE8: %s criteria found", len(decision_tree_criteria))

    for criterion in decision_tree_criteria:
        source_pk, source_title = criterion.pk, criterion.backend_title

        # 1. The existing rows hold the decision tree: they become the
        #    "before régime unique" evaluator, and stop applying on RU day.
        criterion.evaluator = BEFORE_RU
        criterion.backend_title = retitle(source_title, BEFORE_RU_SUFFIX)
        criterion.validity_range = DateRange(None, RU_START_DATE)
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)

        # 2. The "hors régime unique" and "L350-3" criteria are new.
        clone(criterion, HRU, HRU_SUFFIX, DateRange(RU_START_DATE, None))
        clone(criterion, L350_3, L350_3_SUFFIX, DateRange(RU_START_DATE, None))

        # 3. The "régime unique" criterion already exists (created by 0129
        #    alongside the one we just switched); it keeps its evaluator, only
        #    the evaluator's behaviour changed. Create it if it is missing.
        source = Criterion.objects.get(pk=source_pk)
        already_exists = Criterion.objects.filter(
            evaluator=RU,
            regulation=source.regulation,
            activation_map=source.activation_map,
            perimeter=source.perimeter,
        ).exists()
        if not already_exists:
            clone(source, RU, RU_SUFFIX, DateRange(RU_START_DATE, None))

    # 4. Follow the decision tree templates to their new base slug.
    overrides = MoulinetteTemplate.objects.filter(
        key__startswith=OLD_TEMPLATE_PREFIX
    ).exclude(key=KEPT_TEMPLATE_KEY)
    for template in overrides:
        old_key = template.key
        template.key = NEW_TEMPLATE_PREFIX + old_key[len(OLD_TEMPLATE_PREFIX) :]
        template.save()
        logger.info("Update template key: %s => %s", old_key, template.key)


def merge_bcae8(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[HRU, L350_3])
    logger.info("Reverse BCAE8: removing %s criteria", obsolete.count())
    MoulinetteTemplate.objects.filter(criterion__in=obsolete).delete()
    obsolete.delete()

    # Every remaining decision tree criterion goes back to its former name.
    # Bcae8Ru is left alone: it predates this migration.
    for criterion in Criterion.objects.filter(evaluator=BEFORE_RU):
        source_title = criterion.backend_title
        criterion.evaluator = HRU
        criterion.backend_title = retitle(source_title, HRU_SUFFIX)
        criterion.validity_range = None
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)

    for template in MoulinetteTemplate.objects.filter(
        key__startswith=NEW_TEMPLATE_PREFIX
    ):
        old_key = template.key
        template.key = OLD_TEMPLATE_PREFIX + old_key[len(NEW_TEMPLATE_PREFIX) :]
        template.save()
        logger.info("Update template key: %s => %s", old_key, template.key)


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0133_alter_moulinettetemplate_key"),
    ]

    operations = [
        migrations.RunPython(split_bcae8, merge_bcae8),
    ]
