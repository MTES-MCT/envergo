from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand

from envergo.geodata.models import Department


class Command(BaseCommand):
    """Process departments from a shapefile.

    Data source:
    https://www.data.gouv.fr/fr/datasets/contours-des-departements-francais-issus-d-openstreetmap/

    File url:
    https://www.data.gouv.fr/fr/datasets/r/eb36371a-761d-44a8-93ec-3d728bec17ce

    WARNING! This task is not meant to be called several times, since
    metadata can be associated with Department objects in admin after they
    where first imported.

    """

    help = "Importe les départments à partir d'un shapefile."

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
