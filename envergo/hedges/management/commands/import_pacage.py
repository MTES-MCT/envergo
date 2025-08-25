import csv
import os
import pathlib
from decimal import Decimal as D

from django.core.management.base import BaseCommand
from django.db import transaction

from envergo.hedges.models import Pacage


class Command(BaseCommand):
    help = """Update PACAGE data from a csv file.

    The file must be a two column csv.
     - column 1: the pacage number
     - column 2: the exploitation density (floating point number)
    """

    def add_arguments(self, parser):
        parser.add_argument("pacage_csv_file", type=pathlib.Path, nargs=1)

    def handle(self, *args, **options):

        # Read the file
        csv_file = options["pacage_csv_file"][0]
        if not os.path.exists(csv_file):
            return

        pacages = []
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                pacages.append(
                    Pacage(pacage_num=row[0], exploitation_density=D(row[1]))
                )

        with transaction.atomic():
            Pacage.objects.all().delete()
            Pacage.objects.bulk_create(pacages)
