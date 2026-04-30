"""Tests for species habitat CSV import task."""

import pytest

from envergo.geodata.tests.factories import MapFactory
from envergo.hedges.models import Species, SpeciesHabitatFile
from envergo.hedges.tasks import (
    LEVEL_OF_CONCERN_DISPLAY_TO_DB,
    process_species_habitat_row,
)
from envergo.hedges.tests.factories import SpeciesFactory

pytestmark = pytest.mark.django_db


def make_habitat_file():
    """Create a minimal SpeciesHabitatFile for testing."""
    map_obj = MapFactory(map_type="species")
    habitat_file = SpeciesHabitatFile.objects.create(
        name="test",
        map=map_obj,
        file="test.csv",
    )
    return habitat_file


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
    habitat_file = make_habitat_file()
    row = make_row(110920, hedge_types=["mixte", "arbustive"])

    habitat, _ = process_species_habitat_row(row, habitat_file)

    assert habitat.species == species
    assert "mixte" in habitat.hedge_types
    assert "arbustive" in habitat.hedge_types


def test_import_csv_creates_missing_species():
    """When a species with the given CD_REF doesn't exist, create a stub."""
    habitat_file = make_habitat_file()
    row = make_row(99999, hedge_types=["mixte"])

    habitat, _ = process_species_habitat_row(row, habitat_file)

    assert habitat.species.cd_ref == 99999
    assert "99999" in habitat.species.scientific_name
    assert habitat.species.common_name == ""
    assert Species.objects.filter(cd_ref=99999).exists()


def test_import_csv_reads_level_of_concern():
    """level_of_concern from CSV should be stored on SpeciesHabitat."""
    SpeciesFactory(cd_ref=110920)
    habitat_file = make_habitat_file()
    row = make_row(110920, hedge_types=["mixte"], level_of_concern="Fort")

    habitat, _ = process_species_habitat_row(row, habitat_file)

    assert habitat.level_of_concern == "fort"


@pytest.mark.parametrize(
    "display_value,db_value",
    list(LEVEL_OF_CONCERN_DISPLAY_TO_DB.items()),
)
def test_import_csv_maps_display_values(display_value, db_value):
    """CSV display values should be mapped to their database equivalents."""
    SpeciesFactory(cd_ref=42)
    habitat_file = make_habitat_file()
    row = make_row(42, hedge_types=["mixte"], level_of_concern=display_value)

    habitat, _ = process_species_habitat_row(row, habitat_file)

    assert habitat.level_of_concern == db_value


def test_import_csv_saves_groupe_to_adhoc_group():
    """The 'groupe' CSV column should be stored in species.adhoc_group.

    The update is in-memory only — the caller is responsible for persisting
    via bulk_update. This test verifies the in-memory mutation.
    """
    species = SpeciesFactory(cd_ref=110920, adhoc_group="")
    habitat_file = make_habitat_file()
    row = make_row(110920, hedge_types=["mixte"], groupe="Oiseaux")

    _, modified_species = process_species_habitat_row(row, habitat_file)

    assert modified_species is not None
    assert modified_species.pk == species.pk
    assert modified_species.adhoc_group == "Oiseaux"


def test_import_csv_skips_adhoc_group_when_groupe_absent():
    """Species.adhoc_group should not be touched when the CSV has no 'groupe' column."""
    species = SpeciesFactory(cd_ref=110920, adhoc_group="Reptiles")
    habitat_file = make_habitat_file()
    row = make_row(110920, hedge_types=["mixte"])

    _, modified_species = process_species_habitat_row(row, habitat_file)

    assert modified_species is None
    assert species.adhoc_group == "Reptiles"
