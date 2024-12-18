import pytest

from envergo.hedges.models import R
from envergo.hedges.tests.factories import HedgeDataFactory

pytestmark = pytest.mark.django_db


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
