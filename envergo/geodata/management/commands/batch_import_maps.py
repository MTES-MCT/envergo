import csv
import pathlib
from logging import getLogger

from django.core.files import File as DjangoFile
from django.core.management.base import BaseCommand

from envergo.geodata.models import Map
from envergo.geodata.utils import count_features

logger = getLogger(__name__)


class Command(BaseCommand):
    help = """Upload une série de cartes listée dans un CSV.

    This is a one-shot script whose single purpose is to upload all hedges maps all
    at once.

    The csv file must feature those columns:

    file,name,display_name,source,map_type,data_type,description,departments
    """

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=pathlib.Path, nargs=1)
        parser.add_argument("data_dir", type=pathlib.Path, nargs=1)
        parser.add_argument(
            "--purge", action="store_true", help="Purge all existing hedges maps"
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip confirmation prompt for purge",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_file"][0]
        dir_path = options["data_dir"][0]

        if options["purge"]:
            qs = Map.objects.filter(map_type="haies")
            count = qs.count()
            if not options["no_input"]:
                self.stdout.write(
                    self.style.WARNING(f"This will delete {count} existing maps.")
                )
                confirm = input("Are you sure you want to continue? [y/N] ")
                if confirm.lower() != "y":
                    self.stdout.write("Operation cancelled.")
                    return
            self.stdout.write(f"Purging existing {count} maps")
            qs.delete()

        self.stdout.write("Starting to import maps.")

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
            self.stdout.write(f"Importing map {csv_row["file"]}")
            map.file.save(csv_row["file"], map_file)
