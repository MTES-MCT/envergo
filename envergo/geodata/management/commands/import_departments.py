from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand

from envergo.geodata.models import Department


class Command(BaseCommand):
    help = "Importe des zones à partir de shapefiles."

    def add_arguments(self, parser):
        parser.add_argument("shapefile", type=str)

    def handle(self, *args, **options):
        shapefile = options["shapefile"]
        mapping = {
            "department": "code_insee",
            "geometry": "POLYGON",
        }
        lm = LayerMapping(Department, shapefile, mapping)
        lm.save(strict=True)
