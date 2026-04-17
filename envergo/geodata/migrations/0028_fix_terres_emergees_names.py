import os
import re

from django.db import migrations


def fix_terres_emergees_names(apps, schema_editor):
    """Fix the name field of all terres_emergees maps.

    The original CSV import set incorrect names (e.g. "BD_Haie_A26").
    This migration extracts the grid code from each map's filename and
    sets the name to "Délim_terre_France_{code}".

    For example, a file named "delim_terres_france_id_C28_0015.gpkg"
    produces the name "Délim_terre_France_C28".
    """

    Map = apps.get_model("geodata", "Map")
    pattern = re.compile(r"delim_terres_france_id_([A-Z]+\d+)_\d+(?:_[a-zA-Z0-9]+)?\.gpkg")

    queryset = Map.objects.filter(map_type="terres_emergees").only("id", "name", "file")
    for map_obj in queryset.iterator():
        filename = os.path.basename(map_obj.file.name)
        match = pattern.match(filename)
        if not match:
            continue
        map_obj.name = f"Délim_terre_France_{match.group(1)}"
        map_obj.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("geodata", "0027_alter_line_geometry"),
    ]

    operations = [
        migrations.RunPython(
            fix_terres_emergees_names,
            migrations.RunPython.noop,
            elidable=True,
        ),
    ]
