"""Replace legacy slug-form adhoc_group values with human-readable display values.

Before this PR, the `group` field (now renamed `adhoc_group`) used Choices
with slug keys like "mammiferes-terrestres". The template relied on
`get_group_display` to render them as "Mammifères terrestres". After the
field was converted to a plain CharField (migration 0032), the template
switched to `|title`, which loses diacritics and applies wrong casing.

This migration backfills the actual display values so the template can
render `{{ s.adhoc_group }}` directly.
"""

from django.db import migrations

SLUG_TO_DISPLAY = {
    "amphibiens": "Amphibiens",
    "chauves-souris": "Chauves-souris",
    "flore": "Flore",
    "insectes": "Insectes",
    "mammiferes-terrestres": "Mammifères terrestres",
    "oiseaux": "Oiseaux",
    "reptiles": "Reptiles",
}

DISPLAY_TO_SLUG = {v: k for k, v in SLUG_TO_DISPLAY.items()}


def backfill_display_values(apps, schema_editor):
    Species = apps.get_model("hedges", "Species")
    for slug, display in SLUG_TO_DISPLAY.items():
        Species.objects.filter(adhoc_group=slug).update(adhoc_group=display)


def restore_slug_values(apps, schema_editor):
    Species = apps.get_model("hedges", "Species")
    for display, slug in DISPLAY_TO_SLUG.items():
        Species.objects.filter(adhoc_group=display).update(adhoc_group=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0035_alter_species_common_name_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_display_values, restore_slug_values),
    ]
