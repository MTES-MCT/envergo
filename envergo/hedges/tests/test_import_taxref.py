"""Tests for the import_taxref management command."""

import csv
import io
import os
import zipfile
from tempfile import TemporaryDirectory

import pytest
from django.core.management import call_command

from envergo.hedges.models import Species
from envergo.hedges.tests.factories import SpeciesFactory

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
        zip_path = create_taxref_zip(tmpdir, [
            {
                "REGNE": "Plantae",
                "GROUP2_INPN": "Angiospermes",
                "CD_NOM": "110920",
                "CD_REF": "110920",
                "LB_NOM": "Orchis militaris",
                "NOM_VERN": "Orchis militaire, Casque militaire",
                "GROUP1_INPN": "",
            },
        ])
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.cd_ref == 110920


def test_import_taxref_populates_taxref_group():
    """Species should get taxref_group from GROUP2_INPN."""
    SpeciesFactory(scientific_name="Orchis militaris", cd_ref=None)

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [
            {
                "REGNE": "Plantae",
                "GROUP2_INPN": "Angiospermes",
                "CD_NOM": "110920",
                "CD_REF": "110920",
                "LB_NOM": "Orchis militaris",
                "NOM_VERN": "Orchis militaire",
                "GROUP1_INPN": "",
            },
        ])
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.taxref_group == "Angiospermes"


def test_import_taxref_populates_common_name_from_nom_vern():
    """Blank common_name should be filled from NOM_VERN (first name before comma)."""
    SpeciesFactory(
        scientific_name="Orchis militaris",
        common_name="",
        cd_ref=None,
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [
            {
                "REGNE": "Plantae",
                "GROUP2_INPN": "Angiospermes",
                "CD_NOM": "110920",
                "CD_REF": "110920",
                "LB_NOM": "Orchis militaris",
                "NOM_VERN": "Orchis militaire, Casque militaire, Orchis casqué",
                "GROUP1_INPN": "",
            },
        ])
        call_command("import_taxref", zip_path)

    species = Species.objects.get(scientific_name="Orchis militaris")
    assert species.common_name == "Orchis militaire"


def test_import_taxref_matches_by_cd_ref():
    """Species with only a cd_ref (stub from CSV import) should be matched and enriched."""
    SpeciesFactory(
        cd_ref=110920,
        scientific_name="CD_REF_110920",
        common_name="CD_REF_110920",
    )

    with TemporaryDirectory() as tmpdir:
        zip_path = create_taxref_zip(tmpdir, [
            {
                "REGNE": "Plantae",
                "GROUP2_INPN": "Angiospermes",
                "CD_NOM": "110920",
                "CD_REF": "110920",
                "LB_NOM": "Orchis militaris",
                "NOM_VERN": "Orchis militaire",
                "GROUP1_INPN": "",
            },
        ])
        call_command("import_taxref", zip_path)

    species = Species.objects.get(cd_ref=110920)
    assert species.scientific_name == "Orchis militaris"
    assert species.common_name == "Orchis militaire"
    assert species.kingdom == "plantae"
    assert species.taxref_group == "Angiospermes"
