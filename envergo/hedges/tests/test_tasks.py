"""Tests for species map CSV import task."""

import pytest

from envergo.geodata.tests.factories import MapFactory
from envergo.hedges.models import Species, SpeciesMap, SpeciesMapFile
from envergo.hedges.tasks import LEVEL_OF_CONCERN_DISPLAY_TO_DB, process_species_file_map_row
from envergo.hedges.tests.factories import SpeciesFactory

pytestmark = pytest.mark.django_db


def make_smf():
    """Create a minimal SpeciesMapFile-like object for testing."""
    map_obj = MapFactory(map_type="species")
    smf = SpeciesMapFile.objects.create(
        name="test",
        map=map_obj,
        file="test.csv",
    )
    return smf


def make_row(cd_ref, hedge_types=None, level_of_concern="", **extras):
    """Build a CSV row dict matching the new RU format."""
    row = {
        "CD_REF": str(cd_ref),
        "departement": "14",
        "degradee": "",
        "buissonnante": "",
        "arbustive": "",
        "mixte": "",
        "alignement": "",
        "proximite_mare": "",
        "vieil_arbre": "",
        "level_of_concern": level_of_concern,
        "highly_sensitive": "",
    }
    if hedge_types:
        for ht in hedge_types:
            row[ht] = "TRUE"
    row.update(extras)
    return row


def test_import_csv_with_cd_ref():
    """Species should be found by CD_REF."""
    species = SpeciesFactory(cd_ref=110920)
    smf = make_smf()
    row = make_row(110920, hedge_types=["mixte", "arbustive"])

    sm = process_species_file_map_row(row, smf)

    assert sm.species == species
    assert "mixte" in sm.hedge_types
    assert "arbustive" in sm.hedge_types


def test_import_csv_creates_missing_species():
    """When a species with the given CD_REF doesn't exist, create a stub."""
    smf = make_smf()
    row = make_row(99999, hedge_types=["mixte"])

    sm = process_species_file_map_row(row, smf)

    assert sm.species.cd_ref == 99999
    # Stub has placeholder names
    assert "99999" in sm.species.scientific_name
    assert Species.objects.filter(cd_ref=99999).exists()


def test_import_csv_reads_level_of_concern():
    """level_of_concern from CSV should be stored on SpeciesMap."""
    SpeciesFactory(cd_ref=110920)
    smf = make_smf()
    row = make_row(110920, hedge_types=["mixte"], level_of_concern="Fort")

    sm = process_species_file_map_row(row, smf)

    assert sm.level_of_concern == "fort"


@pytest.mark.parametrize(
    "display_value,db_value",
    list(LEVEL_OF_CONCERN_DISPLAY_TO_DB.items()),
)
def test_import_csv_maps_display_values(display_value, db_value):
    """CSV display values should be mapped to their database equivalents."""
    SpeciesFactory(cd_ref=42)
    smf = make_smf()
    row = make_row(42, hedge_types=["mixte"], level_of_concern=display_value)

    sm = process_species_file_map_row(row, smf)

    assert sm.level_of_concern == db_value
