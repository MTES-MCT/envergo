import csv
import glob
import io
import os
import zipfile
from tempfile import TemporaryDirectory

import requests
from django.core.management.base import BaseCommand

from envergo.hedges.models import Species

# Download link can be found here
# https://inpn.mnhn.fr/telechargement/referentielEspece/referentielTaxo
TAXREF_URL = "https://inpn.mnhn.fr/docs-web/docs/download/454260"


class Command(BaseCommand):
    help = "Update species data with TaxRef identifiers (cd_nom)."

    def add_arguments(self, parser):
        parser.add_argument("taxref_url", type=str, nargs="?", default=TAXREF_URL)

    def handle(self, *args, **options):

        # Read the taxref file
        taxref_url = options["taxref_url"]
        if os.path.exists(taxref_url):
            with open(taxref_url, "rb") as f:
                file_content = io.BytesIO(f.read())
        else:
            r = requests.get(taxref_url, stream=True)
            file_content = io.BytesIO(r.content)

        with TemporaryDirectory() as tmpdir:
            zf = zipfile.ZipFile(file_content)
            zf.extractall(tmpdir)

            paths = glob.glob(f"{tmpdir}/TAXREF*.txt")
            try:
                path = paths[0]
            except IndexError:
                self.stderr.write(self.style.ERROR("No TAXREF file found"))
                return

            # Reset taxref ids for all species
            Species.objects.update(taxref_ids=[])
            species_names = Species.objects.all().values_list(
                "scientific_name", flat=True
            )

            with open(path) as csvfile:
                reader = csv.DictReader(csvfile, delimiter="\t")
                for row in reader:
                    scientific_name = row["LB_NOM"]
                    vernacular_name_id = row["CD_NOM"]
                    if scientific_name in species_names:
                        # AFAIK, there is still no way to update an array field in a
                        # sigle query. Issue open since 9 years
                        # https://code.djangoproject.com/ticket/26355
                        species = Species.objects.get(scientific_name=scientific_name)
                        species.taxref_ids.append(vernacular_name_id)
                        species.save()
