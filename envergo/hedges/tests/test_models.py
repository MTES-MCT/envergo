from unittest.mock import patch

import pytest
from shapely import centroid

from envergo.geodata.conftest import aisne_map, calvados_map  # noqa
from envergo.hedges.models import Species
from envergo.hedges.tests.factories import (
    HedgeDataFactory,
    HedgeFactory,
    SpeciesMapFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cleanup():
    # Remove demo species
    Species.objects.all().delete()


@pytest.fixture
def aisne_hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.571258332741955, "lng": 3.613762429205578},
                    {"lat": 49.57123937690368, "lng": 3.613863328804695},
                ],
                "additionalData": {
                    "typeHaie": "degradee",
                    "vieilArbre": True,
                    "proximiteMare": False,
                    "surParcellePac": True,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.57154029531499, "lng": 3.6139268852842137},
                    {"lat": 49.57134548129514, "lng": 3.6138314019310296},
                ],
                "additionalData": {
                    "typeHaie": "arbustive",
                    "vieilArbre": False,
                    "proximiteMare": True,
                    "surParcellePac": False,
                    "proximitePointEau": True,
                    "connexionBoisement": False,
                },
            },
        ]
    )
    return hedge_data


@pytest.fixture
def calvados_hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.187457248991315, "lng": -0.3704281832567369},
                    {"lat": 49.18726791868085, "lng": -0.3697896493669539},
                    {"lat": 49.18677355278797, "lng": -0.36971989356386026},
                    {"lat": 49.18668940491001, "lng": -0.3697842835359544},
                ],
                "additionalData": {
                    "typeHaie": "degradee",
                    "vieilArbre": True,
                    "proximiteMare": True,
                    "surParcellePac": True,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.187352065574956, "lng": -0.3704711099047931},
                    {"lat": 49.18668239258037, "lng": -0.3712706187247817},
                ],
                "additionalData": {
                    "typeHaie": "alignement",
                    "vieilArbre": True,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": True,
                },
            },
        ]
    )
    return hedge_data


def test_hedge_species_are_filtered_by_geography(
    aisne_map, calvados_map, aisne_hedge_data, calvados_hedge_data  # noqa
):
    aisne_species = SpeciesMapFactory(map=aisne_map).species
    calvados_species = SpeciesMapFactory(map=calvados_map).species

    hedge = calvados_hedge_data.hedges()[0]
    assert set(hedge.get_species()) == set([calvados_species])

    hedge = aisne_hedge_data.hedges()[0]
    assert set(hedge.get_species()) == set([aisne_species])


def test_hedge_data_species_are_filtered_by_geography(
    aisne_map, calvados_map, aisne_hedge_data, calvados_hedge_data  # noqa
):
    aisne_species = SpeciesMapFactory(map=aisne_map).species
    calvados_species = SpeciesMapFactory(map=calvados_map).species

    assert set(calvados_hedge_data.get_all_species()) == set([calvados_species])
    assert set(aisne_hedge_data.get_all_species()) == set([aisne_species])


def test_species_are_filtered_by_hedge_type():
    s1 = SpeciesMapFactory(hedge_types=["degradee"]).species
    s2 = SpeciesMapFactory(hedge_types=["degradee"]).species
    s3 = SpeciesMapFactory(hedge_types=["arbustive"]).species
    hedge = HedgeFactory(additionalData__type_haie="degradee")
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_all_species()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species

    hedge = HedgeFactory(additionalData__type_haie="arbustive")
    hedges = HedgeDataFactory(hedges=[hedge])
    hedges_species = hedges.get_all_species()
    assert s1 not in hedges_species
    assert s2 not in hedges_species
    assert s3 in hedges_species


@patch("envergo.hedges.models.get_department_from_coords")
def test_hedges_has_centroid_and_department(mock_get_department):
    hedge = HedgeDataFactory()
    centroid_to_remove = hedge.get_centroid_to_remove()
    centroid_computed = centroid(hedge.hedges_to_remove()[0].geometry)

    assert centroid_to_remove == centroid_computed

    mock_get_department.return_value = "34"
    department = hedge.get_department()

    assert department == "34"


def test_species_are_filtered_by_hedge_features():
    s1 = SpeciesMapFactory(proximite_mare=True, vieil_arbre=True).species
    s2 = SpeciesMapFactory(proximite_mare=True, vieil_arbre=False).species
    s3 = SpeciesMapFactory(proximite_mare=False, vieil_arbre=True).species
    s4 = SpeciesMapFactory(proximite_mare=False, vieil_arbre=False).species

    hedge = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s1, s2, s3, s4])


def test_multiple_hedges_combine_their_species():
    _ = SpeciesMapFactory(proximite_mare=True, vieil_arbre=True).species
    s2 = SpeciesMapFactory(proximite_mare=True, vieil_arbre=False).species
    s3 = SpeciesMapFactory(proximite_mare=False, vieil_arbre=True).species
    s4 = SpeciesMapFactory(proximite_mare=False, vieil_arbre=False).species

    hedge1 = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=False
    )
    hedge_species = hedge1.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge2 = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=True
    )
    hedge_species = hedge2.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedges = HedgeDataFactory(hedges=[hedge1, hedge2])
    all_species = hedges.get_all_species()
    assert set(all_species) == set([s2, s3, s4])
