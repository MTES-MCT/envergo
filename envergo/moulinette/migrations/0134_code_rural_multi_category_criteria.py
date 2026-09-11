"""Split the Code rural criterion into per hedge category evaluators.

Until now, a single evaluator (``CodeRural``) carried the Code rural L126-3
criterion for every hedge category, always returning "a_verifier". The
evaluator is now tripled, one per category, with the same result:

- ``CodeRuralHru``  — hors régime unique (the historical evaluator, renamed)
- ``CodeRuralRu``   — régime unique
- ``CodeRuralL3503``— L350-3
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

MODULE = "envergo.moulinette.regulations.code_rural_haie"

OLD = f"{MODULE}.CodeRural"
HRU = f"{MODULE}.CodeRuralHru"
RU = f"{MODULE}.CodeRuralRu"
L350_3 = f"{MODULE}.CodeRuralL3503"

HRU_SUFFIX = "Hors régime unique"
RU_SUFFIX = "Régime unique"
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


def split_code_rural(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")

    criteria = list(Criterion.objects.filter(evaluator=OLD))
    logger.info("Migrating Code rural: %s criteria found", len(criteria))

    for criterion in criteria:
        source_title = criterion.backend_title

        # 1. The existing row becomes the "hors régime unique" evaluator.
        criterion.evaluator = HRU
        criterion.backend_title = retitle(source_title, HRU_SUFFIX)
        criterion.save()
        logger.info("Update: %s => %s", source_title, criterion.backend_title)

        # 2. The "régime unique" and "L350-3" criteria are new clones.
        clone(criterion, RU, RU_SUFFIX)
        clone(criterion, L350_3, L350_3_SUFFIX)


def merge_code_rural(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")

    # The criteria created above have no admin-authored template of their own,
    # but deleting a criterion a template points at is protected, so be explicit.
    obsolete = Criterion.objects.filter(evaluator__in=[RU, L350_3])
    logger.info("Reverse Code rural: removing %s criteria", obsolete.count())
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
        ("moulinette", "0133_alter_moulinettetemplate_key"),
    ]

    operations = [
        migrations.RunPython(split_code_rural, merge_code_rural),
    ]
