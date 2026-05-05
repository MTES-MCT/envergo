"""Tests for the import_taxref management command."""

import csv
import os
import zipfile
from tempfile import TemporaryDirectory

import pytest
from django.core.management import call_command

from envergo.hedges.models import Species, SpeciesHabitat
from envergo.hedges.tests.factories import SpeciesFactory, SpeciesHabitatFactory

pytestmark = pytest.mark.django_db


def create_taxref_zip(tmpdir, rows):
    """Create a minimal TaxRef ZIP file with the given data rows.

    Each row is a dict with keys matching TaxRef columns.
    """
    fieldnames = [
        "REGNE",
        "GROUP1_INPN",
        "GROUP2_INPN",
        "CD_NOM",
        "CD_REF",
        "LB_NOM",
        "NOM_VERN",
    ]
    txt_path = os.path.join(tmpdir, "TAXREFv99.txt")
    with open(txt_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    zip_path = os.path.join(tmpdir, "taxref.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(txt_path, "TAXREFv99.txt")

    return zip_path


def test_import_taxref_populates_cd_ref():
    """Species matched by scientific_name should get cd_ref populated."""
    SpeciesFactory(scientific_name="Orchis militaris", cd_ref=None)

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(
            tmpdir,
            [
                {
                    "REGNE": "Plantae",
                    "GROUP2_INPN": "Angiospermes",
                    "CD_NOM": "110920",
                    "CD_REF": "110920",
                    "LB_NOM": "Orchis militaris",
                    "NOM_VERN": "Orchis militaire, Casque militaire",
                    "GROUP1_INPN": "",
                },
            ],
        )
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.cd_ref == 110920


def test_import_taxref_populates_group():
    """Species should get group from GROUP2_INPN."""
    SpeciesFactory(scientific_name="Orchis militaris", cd_ref=None)

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(
            tmpdir,
            [
                {
                    "REGNE": "Plantae",
                    "GROUP2_INPN": "Angiospermes",
                    "CD_NOM": "110920",
                    "CD_REF": "110920",
                    "LB_NOM": "Orchis militaris",
                    "NOM_VERN": "Orchis militaire",
                    "GROUP1_INPN": "",
                },
            ],
        )
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.group == "Angiospermes"


def test_import_taxref_populates_common_name_from_nom_vern():
    """Blank common_name should be filled from NOM_VERN (first name before comma)."""
    SpeciesFactory(
        scientific_name="Orchis militaris",
        common_name="",
        cd_ref=None,
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(
            tmpdir,
            [
                {
                    "REGNE": "Plantae",
                    "GROUP2_INPN": "Angiospermes",
                    "CD_NOM": "110920",
                    "CD_REF": "110920",
                    "LB_NOM": "Orchis militaris",
                    "NOM_VERN": "Orchis militaire, Casque militaire, Orchis casqué",
                    "GROUP1_INPN": "",
                },
            ],
        )
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.common_name == "Orchis militaire"


def test_import_taxref_matches_by_cd_ref():
    """Species with only a cd_ref (stub from CSV import) should be matched and enriched."""
    SpeciesFactory(
        cd_ref=110920,
        scientific_name="CD_REF_110920",
        common_name="",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(
            tmpdir,
            [
                {
                    "REGNE": "Plantae",
                    "GROUP2_INPN": "Angiospermes",
                    "CD_NOM": "110920",
                    "CD_REF": "110920",
                    "LB_NOM": "Orchis militaris",
                    "NOM_VERN": "Orchis militaire",
                    "GROUP1_INPN": "",
                },
            ],
        )
        call_command("import_taxref", zip_path)

    species = Species.objects.get(cd_ref=110920)
    assert species.scientific_name == "Orchis militaris"
    assert species.common_name == "Orchis militaire"
    assert species.kingdom == "plantae"
    assert species.group == "Angiospermes"


def test_import_taxref_leaves_common_name_blank_when_no_nom_vern():
    """Species with empty NOM_VERN in TaxRef should keep a blank common_name."""
    SpeciesFactory(
        cd_ref=6124,
        scientific_name="CD_REF_6124",
        common_name="",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(
            tmpdir,
            [
                {
                    "REGNE": "Plantae",
                    "GROUP2_INPN": "Mousses",
                    "CD_NOM": "6124",
                    "CD_REF": "6124",
                    "LB_NOM": "Rhytidium rugosum",
                    "NOM_VERN": "",
                    "GROUP1_INPN": "",
                },
            ],
        )
        call_command("import_taxref", zip_path)

    species = Species.objects.get(cd_ref=6124)
    assert species.scientific_name == "Rhytidium rugosum"
    assert species.common_name == ""


TAXREF_ROW_UPUPA = {
    "REGNE": "Animalia",
    "GROUP2_INPN": "Oiseaux",
    "CD_NOM": "3571",
    "CD_REF": "3571",
    "LB_NOM": "Upupa epops",
    "NOM_VERN": "Huppe fasciée",
    "GROUP1_INPN": "",
}


def test_merge_stub_into_legacy_species():
    """A stub matched by cd_ref is merged into the legacy species that holds the real name."""
    SpeciesFactory(
        scientific_name="Upupa epops",
        common_name="Huppe fasciée",
        cd_ref=None,
    )
    SpeciesFactory(
        cd_ref=3571,
        scientific_name="CD_REF_3571",
        common_name="",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [TAXREF_ROW_UPUPA])
        call_command("import_taxref", zip_path)

    assert Species.objects.count() == 1
    species = Species.objects.get()
    assert species.scientific_name == "Upupa epops"
    assert species.common_name == "Huppe fasciée"
    assert species.cd_ref == 3571
    assert species.kingdom == "animalia"
    assert species.group == "Oiseaux"
    assert 3571 in species.cd_noms


def test_merge_reassigns_species_habitat():
    """SpeciesHabitat rows from the stub are reassigned to the keeper."""
    legacy = SpeciesFactory(
        scientific_name="Upupa epops",
        common_name="Huppe fasciée",
        cd_ref=None,
    )
    stub = SpeciesFactory(
        cd_ref=3571,
        scientific_name="CD_REF_3571",
        common_name="",
    )
    legacy_habitat = SpeciesHabitatFactory(species=legacy)
    stub_habitat = SpeciesHabitatFactory(species=stub)
    stub_habitat_pk = stub_habitat.pk

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [TAXREF_ROW_UPUPA])
        call_command("import_taxref", zip_path)

    assert Species.objects.count() == 1
    keeper = Species.objects.get()
    assert keeper.habitats.count() == 2

    reassigned = SpeciesHabitat.objects.get(pk=stub_habitat_pk)
    assert reassigned.species == keeper


def test_merge_keeps_legacy_habitat_on_conflict():
    """When both species have a habitat for the same map, the legacy one is kept."""
    legacy = SpeciesFactory(
        scientific_name="Upupa epops",
        common_name="Huppe fasciée",
        cd_ref=None,
    )
    stub = SpeciesFactory(
        cd_ref=3571,
        scientific_name="CD_REF_3571",
        common_name="",
    )
    legacy_habitat = SpeciesHabitatFactory(species=legacy)
    SpeciesHabitatFactory(species=stub, map=legacy_habitat.map)

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [TAXREF_ROW_UPUPA])
        call_command("import_taxref", zip_path)

    assert Species.objects.count() == 1
    keeper = Species.objects.get()
    assert keeper.habitats.count() == 1
    assert keeper.habitats.get().pk == legacy_habitat.pk


def test_merge_preserves_legacy_common_name():
    """The keeper's existing common_name is never overwritten by TaxRef data."""
    SpeciesFactory(
        scientific_name="Upupa epops",
        common_name="Huppe d'Afrique",
        cd_ref=None,
    )
    SpeciesFactory(
        cd_ref=3571,
        scientific_name="CD_REF_3571",
        common_name="",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [TAXREF_ROW_UPUPA])
        call_command("import_taxref", zip_path)

    species = Species.objects.get()
    assert species.common_name == "Huppe d'Afrique"


def test_no_merge_when_both_have_cd_ref():
    """Two species that both have cd_ref values are not merged — the warning is kept."""
    SpeciesFactory(
        scientific_name="Upupa epops",
        cd_ref=9999,
    )
    SpeciesFactory(
        cd_ref=3571,
        scientific_name="CD_REF_3571",
        common_name="",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [TAXREF_ROW_UPUPA])
        call_command("import_taxref", zip_path)

    assert Species.objects.count() == 2
    stub = Species.objects.get(cd_ref=3571)
    assert stub.scientific_name == "CD_REF_3571"
