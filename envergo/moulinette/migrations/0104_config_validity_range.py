import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
from django.db import migrations, models
from django.db.models.functions import Coalesce
from django.db.backends.postgresql.psycopg_any import DateRange


def convert_config_dates_to_range(apps, schema_editor):
    """Convert valid_from/valid_until to validity_range for both Config models."""
    for model_name in ("ConfigAmenagement", "ConfigHaie"):
        Model = apps.get_model("moulinette", model_name)
        for config in Model.objects.all():
            if config.valid_from is not None or config.valid_until is not None:
                config.validity_range = DateRange(
                    config.valid_from, config.valid_until, "[)"
                )
            else:
                config.validity_range = None
            config.save(update_fields=["validity_range"])


def convert_range_to_config_dates(apps, schema_editor):
    """Reverse: convert validity_range back to valid_from/valid_until."""
    for model_name in ("ConfigAmenagement", "ConfigHaie"):
        Model = apps.get_model("moulinette", model_name)
        for config in Model.objects.all():
            if config.validity_range is not None:
                config.valid_from = config.validity_range.lower
                config.valid_until = config.validity_range.upper
            else:
                config.valid_from = None
                config.valid_until = None
            config.save(update_fields=["valid_from", "valid_until"])


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0101_config_no_overlap_constraint"),
        ("moulinette", "0103_remove_criterion_validity_date_end_gt_start_and_more"),
    ]

    operations = [
        # Step 1: Remove old constraints
        migrations.RemoveConstraint(
            model_name="configamenagement",
            name="configamenagement_valid_dates_order",
        ),
        migrations.RemoveConstraint(
            model_name="configamenagement",
            name="configamenagement_no_overlapping_validity",
        ),
        migrations.RemoveConstraint(
            model_name="confighaie",
            name="confighaie_valid_dates_order",
        ),
        migrations.RemoveConstraint(
            model_name="confighaie",
            name="confighaie_no_overlapping_validity",
        ),
        # Step 2: Add validity_range field
        migrations.AddField(
            model_name="configamenagement",
            name="validity_range",
            field=django.contrib.postgres.fields.ranges.DateRangeField(
                blank=True, null=True, verbose_name="Dates de validité"
            ),
        ),
        migrations.AddField(
            model_name="confighaie",
            name="validity_range",
            field=django.contrib.postgres.fields.ranges.DateRangeField(
                blank=True, null=True, verbose_name="Dates de validité"
            ),
        ),
        # Step 3: Data migration
        migrations.RunPython(
            convert_config_dates_to_range,
            convert_range_to_config_dates,
        ),
        # Step 4: Remove old fields
        migrations.RemoveField(
            model_name="configamenagement",
            name="valid_from",
        ),
        migrations.RemoveField(
            model_name="configamenagement",
            name="valid_until",
        ),
        migrations.RemoveField(
            model_name="confighaie",
            name="valid_from",
        ),
        migrations.RemoveField(
            model_name="confighaie",
            name="valid_until",
        ),
        # Step 5: Add new constraints
        migrations.AddConstraint(
            model_name="configamenagement",
            constraint=models.CheckConstraint(
                check=models.Q(("validity_range__isempty", False)),
                name="configamenagement_validity_range_non_empty",
                violation_error_message="La date de fin de validité doit être supérieure à la date de début.",
            ),
        ),
        migrations.AddConstraint(
            model_name="configamenagement",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                expressions=[
                    ("department", "="),
                    (
                        Coalesce(
                            "validity_range",
                            models.Value(DateRange(None, None, "[)")),
                        ),
                        "&&",
                    ),
                ],
                name="configamenagement_no_overlapping_validity",
                violation_error_message="Cette configuration chevauche une configuration existante pour ce département.",
            ),
        ),
        migrations.AddConstraint(
            model_name="confighaie",
            constraint=models.CheckConstraint(
                check=models.Q(("validity_range__isempty", False)),
                name="confighaie_validity_range_non_empty",
                violation_error_message="La date de fin de validité doit être supérieure à la date de début.",
            ),
        ),
        migrations.AddConstraint(
            model_name="confighaie",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                expressions=[
                    ("department", "="),
                    (
                        Coalesce(
                            "validity_range",
                            models.Value(DateRange(None, None, "[)")),
                        ),
                        "&&",
                    ),
                ],
                name="confighaie_no_overlapping_validity",
                violation_error_message="Cette configuration chevauche une configuration existante pour ce département.",
            ),
        ),
        # Step 6: Add Criterion ExclusionConstraint
        migrations.AddConstraint(
            model_name="criterion",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                expressions=[
                    ("evaluator", "="),
                    ("activation_map", "="),
                    ("regulation", "="),
                    (
                        Coalesce("perimeter", models.Value(0)),
                        "=",
                    ),
                    (
                        Coalesce(
                            "validity_range",
                            models.Value(DateRange(None, None, "[)")),
                        ),
                        "&&",
                    ),
                ],
                name="criterion_no_overlapping_validity",
                violation_error_message="Ce critère chevauche un critère existant avec le même évaluateur, la même carte d'activation et la même réglementation.",
            ),
        ),
    ]
