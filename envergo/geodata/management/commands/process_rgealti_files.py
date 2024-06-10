import os
from argparse import ArgumentTypeError
from pathlib import Path

from django.core.management.base import BaseCommand

from envergo.geodata.models import RGEAltiDptProcess

# Departments must be processed in this order
PROCESS_ORDER = [
    "33",
    "01",
    "37",
    "67",
    "10",
    "24",
    "19",
    "14",
    "80",
    "78",
    "95",
    "60",
    "49",
    "76",
    "50",
    "59",
    "62",
    "77",
    "91",
    "40",
    "02",
    "17",
    "22",
    "35",
    "44",
    "56",
    "28",
    "80",
    "61",
    "36",
    "79",
    "45",
    "72",
    "86",
    "23",
]


def dir_path(path):
    if os.path.isdir(path):
        return Path(path)
    else:
        raise ArgumentTypeError(f"{path} is not a valid path.")


class Command(BaseCommand):
    """Process all known rge alti files.

    This script is a helper tool that aim to ease the process of running
    the mass_carto_creation tool on several rge alti files.

    """

    help = "Traite les fichiers rge alti"

    def add_arguments(self, parser):
        parser.add_argument("dir_path", type=dir_path)
        parser.add_argument("output_path", type=dir_path)
        parser.add_argument("department", nargs="*", type=str)

    def handle(self, *args, **options):
        alti_files_dir = options["dir_path"]
        output_dir = options["output_path"]
        departments = options["department"]

        for dept in PROCESS_ORDER:

            if departments and dept not in departments:
                continue

            self.stdout.write(f"\n\n\nProcessing dept {dept}")
            process = RGEAltiDptProcess.objects.filter(department=dept).first()
            if process and process.done:
                self.stdout.write(f"Dept {dept} already processed, skipping")
                continue

            alti_file_pattern = f"RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D0{dept}_*.7z"
            try:
                alti_file = list(alti_files_dir.glob(alti_file_pattern))[0]
                self.stdout.write(f"Found alti file {alti_file} for dept {dept}")
            except IndexError:
                self.stderr.write(f"Missing alti file for dept {dept}. Skipping.")
                continue

            process, _created = RGEAltiDptProcess.objects.update_or_create(
                department=dept, defaults={"filename": alti_file}
            )

            output_path = os.path.join(output_dir, f"dept_{dept}")
            if not os.path.exists(output_path):
                os.mkdir(output_path)
            process.start(output_path)
