"""Migrate single_procedure_settings from flat per-type coefficients to zone-based format.

Old format:
    {"coeff_compensation": {"degradee": 1.0, "buissonnante": 1.0, "arbustive": 1.0, "mixte": 1.0}}

New format:
    {"coeff_compensation": {"default": {"X_densite": 60, "R1_non_arboree_HD": 1.0, ...}}}
"""

from django.db import migrations


def migrate_coeff_compensation_forward(apps, schema_editor):
    """Convert flat per-type coefficients into the zone-based format.

    Maps the old ``mixte`` coefficient to ``R3/R4_arboree_*`` and averages
    the remaining types (``degradee``, ``buissonnante``, ``arbustive``) for
    ``R1/R2_non_arboree_*``. Uses a default ``X_densite`` of 60 since the
    old format had no density threshold concept.
    """
    ConfigHaie = apps.get_model("moulinette", "ConfigHaie")

    for config in ConfigHaie.objects.filter(single_procedure=True):
        settings = config.single_procedure_settings or {}
        old_coeff = settings.get("coeff_compensation", {})

        # Skip configs already in the new format (idempotency)
        if "default" in old_coeff and isinstance(old_coeff["default"], dict):
            continue

        # Skip configs with no old-format data
        if not old_coeff or "mixte" not in old_coeff:
            continue

        arboree = float(old_coeff.get("mixte", 1.0))
        non_arboree_values = [
            float(old_coeff.get(t, 1.0))
            for t in ("degradee", "buissonnante", "arbustive")
            if t in old_coeff
        ]
        non_arboree = (
            sum(non_arboree_values) / len(non_arboree_values)
            if non_arboree_values
            else 1.0
        )

        config.single_procedure_settings = {
            "coeff_compensation": {
                "default": {
                    "X_densite": 60,
                    "R1_non_arboree_HD": non_arboree,
                    "R2_non_arboree_LD": non_arboree,
                    "R3_arboree_HD": arboree,
                    "R4_arboree_LD": arboree,
                }
            }
        }
        config.save(update_fields=["single_procedure_settings"])


def migrate_coeff_compensation_backward(apps, schema_editor):
    """Revert to the flat per-type coefficient format.

    Since the old format had no density-based distinction, we collapse
    ``arboree_HD`` back to ``mixte`` and ``non_arboree_HD`` to the three
    non-arboree types.
    """
    ConfigHaie = apps.get_model("moulinette", "ConfigHaie")

    for config in ConfigHaie.objects.filter(single_procedure=True):
        settings = config.single_procedure_settings or {}
        coeff = settings.get("coeff_compensation", {})
        default = coeff.get("default")

        if not isinstance(default, dict):
            continue

        arboree = default.get("R3_arboree_HD", 1.0)
        non_arboree = default.get("R1_non_arboree_HD", 1.0)

        config.single_procedure_settings = {
            "coeff_compensation": {
                "degradee": non_arboree,
                "buissonnante": non_arboree,
                "arbustive": non_arboree,
                "mixte": arboree,
            }
        }
        config.save(update_fields=["single_procedure_settings"])


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0111_update_coeff_compensation_constraint"),
    ]

    operations = [
        migrations.RunPython(
            migrate_coeff_compensation_forward,
            migrate_coeff_compensation_backward,
        ),
    ]
