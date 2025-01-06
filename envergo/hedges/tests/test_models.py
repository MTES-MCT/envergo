import pytest

from envergo.hedges.models import R
from envergo.hedges.tests.factories import (
    HedgeDataFactory,
    HedgeFactory,
    SpeciesFactory,
)

pytestmark = pytest.mark.django_db


def test_species_are_filtered_by_hedge_type():
    s1 = SpeciesFactory(hedge_types=["degradee"])
    s2 = SpeciesFactory(hedge_types=["degradee"])
    s3 = SpeciesFactory(hedge_types=["arbustive"])
    hedge = HedgeFactory(additionalData__typeHaie="degradee")
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_all_species()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species

    hedge = HedgeFactory(additionalData__typeHaie="arbustive")
    hedges = HedgeDataFactory(hedges=[hedge])
    hedges_species = hedges.get_all_species()
    assert s1 not in hedges_species
    assert s2 not in hedges_species
    assert s3 in hedges_species


def test_species_are_filtered_by_hedge_features():
    s1 = SpeciesFactory(proximite_mare=True, vieil_arbre=True)
    s2 = SpeciesFactory(proximite_mare=True, vieil_arbre=False)
    s3 = SpeciesFactory(proximite_mare=False, vieil_arbre=True)
    s4 = SpeciesFactory(proximite_mare=False, vieil_arbre=False)

    hedge = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s1, s2, s3, s4])


def test_multiple_hedges_combine_their_species():
    _ = SpeciesFactory(proximite_mare=True, vieil_arbre=True)
    s2 = SpeciesFactory(proximite_mare=True, vieil_arbre=False)
    s3 = SpeciesFactory(proximite_mare=False, vieil_arbre=True)
    s4 = SpeciesFactory(proximite_mare=False, vieil_arbre=False)

    hedge1 = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=False
    )
    hedge_species = hedge1.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge2 = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=True
    )
    hedge_species = hedge2.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedges = HedgeDataFactory(hedges=[hedge1, hedge2])
    all_species = hedges.get_all_species()
    assert set(all_species) == set([s2, s3, s4])


def test_minimum_lengths_to_plant():
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.69437648171791, "lng": 3.615381717681885},
                    {"lat": 43.69405067324741, "lng": 3.6149525642395024},
                ],
                "additionalData": {
                    "typeHaie": "degradee",
                    "vieilArbre": False,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694364845731585, "lng": 3.6154152452945714},
                    {"lat": 43.69409430841308, "lng": 3.6150853335857396},
                ],
                "additionalData": {
                    "typeHaie": "buissonnante",
                    "vieilArbre": False,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D3",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.69434739174787, "lng": 3.6154554784297948},
                    {"lat": 43.69414473123166, "lng": 3.615212738513947},
                ],
                "additionalData": {
                    "typeHaie": "arbustive",
                    "vieilArbre": False,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D4",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694328968092876, "lng": 3.615493029356003},
                    {"lat": 43.69419215400783, "lng": 3.6153347790241246},
                ],
                "additionalData": {
                    "typeHaie": "mixte",
                    "vieilArbre": False,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
            {
                "id": "D5",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.69430763543265, "lng": 3.615543991327286},
                    {"lat": 43.694235789068386, "lng": 3.6154729127883916},
                ],
                "additionalData": {
                    "typeHaie": "alignement",
                    "vieilArbre": False,
                    "proximiteMare": False,
                    "surParcellePac": False,
                    "proximitePointEau": False,
                    "connexionBoisement": False,
                },
            },
        ]
    )
    minimum_lengths_to_plant = hedges._get_minimum_lengths_to_plant()

    assert round(minimum_lengths_to_plant["degradee"]) == R * 50
    assert round(minimum_lengths_to_plant["buissonnante"]) == R * 40
    assert round(minimum_lengths_to_plant["arbustive"]) == R * 30
    assert round(minimum_lengths_to_plant["mixte"]) == R * 20
    assert round(minimum_lengths_to_plant["alignement"]) == R * 10
