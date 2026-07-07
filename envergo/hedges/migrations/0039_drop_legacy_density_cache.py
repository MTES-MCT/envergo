from django.db import migrations

LEGACY_KEYS = ["around_lines", "around_centroid"]


def drop_legacy_density_keys(apps, schema_editor):
    """Remove the project-wide density cache entries.

    Densities are now computed and cached per hedge subset, keyed by the
    hedge ids (e.g. "around_lines_D1-D3"). The legacy values were computed
    over ALL hedges to remove, so they must not be reused: dropping them
    forces a correct lazy recompute on next access.
    """
    HedgeData = apps.get_model("hedges", "HedgeData")
    hedges = HedgeData.objects.filter(_density__isnull=False)

    to_update = []
    for hedge in hedges:
        if hedge._density and any(key in hedge._density for key in LEGACY_KEYS):
            for key in LEGACY_KEYS:
                hedge._density.pop(key, None)
            to_update.append(hedge)

    HedgeData.objects.bulk_update(to_update, ["_density"])


class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0038_alter_species_adhoc_group_alter_species_group"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_density_keys, migrations.RunPython.noop),
    ]
