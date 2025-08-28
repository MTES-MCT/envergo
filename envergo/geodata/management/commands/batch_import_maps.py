import csv
import pathlib

from django.core.files import File as DjangoFile
from django.core.management.base import BaseCommand

from envergo.geodata.models import Map
from envergo.geodata.utils import count_features


class Command(BaseCommand):
    help = "Upload une série de cartes"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=pathlib.Path, nargs=1)
        parser.add_argument("data_dir", type=pathlib.Path, nargs=1)

    def handle(self, *args, **options):
        csv_path = options["csv_file"][0]
        dir_path = options["data_dir"][0]

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.process_file(row, dir_path)

    def process_file(self, csv_row, dir_path):
        full_path = dir_path / csv_row["file"]
        with open(full_path, "rb") as f:
            map_file = DjangoFile(f)
            map = Map.objects.create(
                name=csv_row["name"],
                display_name=csv_row["display_name"],
                description=csv_row["description"],
                source=csv_row["source"],
                departments=csv_row["departments"].split(","),
                map_type="haies",
                data_type="certain",  # dedans
                expected_geometries=count_features(map_file),
            )
            map.file.save(csv_row["file"], map_file)
