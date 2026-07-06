from django.db import migrations


def drop_legacy_around_lines_key(apps, schema_editor):
    """Remove the project-wide "around_lines" density cache entry.

    Line-buffer density is now computed and cached per hedge subset, keyed
    by the hedge ids (e.g. "around_lines_D1-D3"). The legacy value was
    computed over ALL hedges to remove, so it must not be reused: dropping
    it forces a correct lazy recompute on next access.
    """
    HedgeData = apps.get_model("hedges", "HedgeData")
    hedges = HedgeData.objects.filter(_density__isnull=False)

    to_update = []
    for hedge in hedges:
        if hedge._density and "around_lines" in hedge._density:
            hedge._density.pop("around_lines")
            to_update.append(hedge)

    HedgeData.objects.bulk_update(to_update, ["_density"])


class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0038_alter_species_adhoc_group_alter_species_group"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_around_lines_key, migrations.RunPython.noop),
    ]
