import pytest

from envergo.hedges.tests.factories import HedgeDataFactory


@pytest.fixture
def hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
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
                    {"lat": 43.694364, "lng": 3.615415},
                    {"lat": 43.694094, "lng": 3.615085},
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
                    {"lat": 43.694347, "lng": 3.615455},
                    {"lat": 43.694144, "lng": 3.615210},
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
                    {"lat": 43.694328, "lng": 3.615493},
                    {"lat": 43.694192, "lng": 3.615332},
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
                    {"lat": 43.694305, "lng": 3.615543},
                    {"lat": 43.694235, "lng": 3.615464},
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
    return hedge_data
