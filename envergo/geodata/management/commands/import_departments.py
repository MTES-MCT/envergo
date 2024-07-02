from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand

from envergo.geodata.models import Department


class Command(BaseCommand):
    """Process departments from a shapefile.

    Data source:
    https://geoservices.ign.fr/adminexpress

    You have to download the "France entière" edition, then extract the file and
    find the DEPARTMENT.* files.

    This task loads data from  a shapefile, and updates existing `Department` objects
    with a new geometry data.

    """

    help = "Importe les départments à partir d'un shapefile."

    def add_arguments(self, parser):
        parser.add_argument("shapefile", type=str)

    def handle(self, *args, **options):
        shapefile = options["shapefile"]
        mapping = {
            "department": "INSEE_DEP",
            "geometry": "POLYGON",
        }
        # The LayerMapping class will add no geometries to the existing MultiPolygonField
        # so we have to reset it first.
        Department.objects.update(geometry=None)
        lm = LayerMapping(Department, shapefile, mapping, unique="department")
        lm.save(strict=True, verbose=True)
