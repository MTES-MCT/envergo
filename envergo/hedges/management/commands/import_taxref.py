import csv
import glob
import io
import os
import zipfile
from tempfile import TemporaryDirectory

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from envergo.hedges.models import Species
from envergo.hedges.species_stubs import has_placeholder_scientific_name

# Download link can be found here
# https://inpn.mnhn.fr/telechargement/referentielEspece/referentielTaxo
# https://www.patrinat.fr/fr/page-temporaire-de-telechargement-des-referentiels-de-donnees-lies-linpn-7353
TAXREF_URL = "https://assets.patrinat.fr/files/referentiel/TAXREF_v18_2025.zip"


class Command(BaseCommand):
    help = "Update species records with official data from the TaxRef document."

    def add_arguments(self, parser):
        parser.add_argument("taxref_url", type=str, nargs="?", default=TAXREF_URL)

    def handle(self, *args, **options):

        # Read the taxref file
        taxref_url = options["taxref_url"]
        if os.path.exists(taxref_url):
            with open(taxref_url, "rb") as f:
                file_content = io.BytesIO(f.read())
        else:
            self.stdout.write("Downloading Taxref file")
            r = requests.get(taxref_url, stream=True)
            file_content = io.BytesIO(r.content)

        with TemporaryDirectory() as tmpdir:
            self.stdout.write("Extracting archive")
            zf = zipfile.ZipFile(file_content)
            zf.extractall(tmpdir)

            paths = glob.glob(f"{tmpdir}/TAXREFv*.txt")
            try:
                path = paths[0]
            except IndexError:
                self.stderr.write(self.style.ERROR("No TAXREF file found"))
                return

            self.run_import(path)

    def run_import(self, path):
        """Enrich all local Species with data from the TaxRef reference file.

        The TaxRef file contains ~1.5M rows (one per cd_nom across all French
        taxa). Most rows don't match any Species in our database. For those
        that do match, we update the record from the taxonomy.

        Matching is done in-memory via two lookup dicts (by cd_ref and by
        scientific_name) to avoid per-row database queries.
        """

        self.stdout.write("Starting Taxref file processing")

        species_index = SpeciesIndex(Species.objects.all())

        with transaction.atomic():
            # Reset cd_nom arrays — they will be rebuilt from the TaxRef file.
            Species.objects.update(cd_noms=[])
            for s in species_index.all():
                s.cd_noms = []

            with open(path) as csvfile:
                reader = csv.DictReader(csvfile, delimiter="\t")
                for row in reader:
                    self.process_row(row, species_index)

            for s in species_index.all():
                s.save()

    def process_row(self, row, species_index):
        """Enrich a single Species from a TaxRef row, if it matches."""

        cd_ref = int(row["CD_REF"])
        scientific_name = row["LB_NOM"]

        species = species_index.find(cd_ref, scientific_name)
        if species is None:
            return

        # Every TaxRef row carries one cd_nom. A single species (cd_ref) can
        # appear in many rows because historical synonyms each have their own
        # cd_nom. We accumulate all of them.
        species.cd_noms.append(int(row["CD_NOM"]))
        species.kingdom = row["REGNE"].lower()

        # Backfill cd_ref on legacy species that were matched by name only
        if species.cd_ref is None:
            species.cd_ref = cd_ref
            species_index.register_cd_ref(cd_ref, species)

        taxref_group = row.get("GROUP2_INPN", "")
        if taxref_group:
            species.group = taxref_group

        self.enrich_stub_names(species, row, species_index)

    def enrich_stub_names(self, species, row, species_index):
        """Replace placeholder names on stub species with real TaxRef data.

        When the RU CSV import creates a Species from a CD_REF alone, it sets
        placeholder names (e.g. "CD_REF_12345") because the
        CSV doesn't carry names. This method fills them in from TaxRef.
        """
        nom_vern = row.get("NOM_VERN", "")
        if nom_vern and not species.common_name:
            # NOM_VERN can contain several names separated by commas;
            # we take the first one.
            species.common_name = nom_vern.split(",")[0].strip()

        scientific_name = row["LB_NOM"]
        if scientific_name and has_placeholder_scientific_name(species):
            species.scientific_name = scientific_name
            species_index.register_scientific_name(scientific_name, species)


class SpeciesIndex:
    """In-memory index for fast Species lookup by cd_ref or scientific_name.

    The TaxRef file has ~1.5M rows but we only care about the few hundred
    Species already in our database. Loading them all into two dicts up front
    turns each row's lookup into an O(1) hash probe instead of a DB query.

    The index is mutable: when a TaxRef row enriches a stub Species (created
    earlier by the CSV import with only a cd_ref), we register its real
    scientific_name so later rows referencing the same name also match.
    """

    def __init__(self, queryset):
        self.by_cd_ref = {}
        self.by_scientific_name = {}
        for s in queryset:
            if s.cd_ref is not None:
                self.by_cd_ref[s.cd_ref] = s
            if s.scientific_name:
                self.by_scientific_name[s.scientific_name] = s

    def find(self, cd_ref, scientific_name):
        """Find a Species by cd_ref first, then by scientific_name."""
        return self.by_cd_ref.get(cd_ref) or self.by_scientific_name.get(
            scientific_name
        )

    def register_cd_ref(self, cd_ref, species):
        """Add a cd_ref entry so subsequent rows with the same cd_ref match."""
        self.by_cd_ref[cd_ref] = species

    def register_scientific_name(self, scientific_name, species):
        """Add a scientific_name entry after a stub's name is replaced."""
        self.by_scientific_name[scientific_name] = species

    def all(self):
        """Return all indexed species (deduplicated)."""
        return set(self.by_cd_ref.values()) | set(self.by_scientific_name.values())
