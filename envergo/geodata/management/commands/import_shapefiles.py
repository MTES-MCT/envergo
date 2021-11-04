from django.contrib.gis.gdal import DataSource
from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand

from envergo.geodata.models import Zone


class Command(BaseCommand):
    help = "Importe des zones à partir de shapefiles."

    def add_arguments(self, parser):
        parser.add_argument("shapefile", type=str)

    def handle(self, *args, **options):
        shapefile = options["shapefile"]
        ds = DataSource(shapefile)
        mapping = {"code": "CODEZONE", "polygon": "POLYGON"}
        lm = LayerMapping(Zone, ds, mapping)
        self.stdout.write(self.style.SUCCESS("Importing"))
        lm.save(verbose=True)
