import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.regulations import NormandieQualityCondition
from envergo.hedges.tests.factories import HedgeDataFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                # ~ 50m
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                    "mode_destruction": "arrachage",
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                    "mode_destruction": "coupe_a_blanc",
                },
            },
            {
                "id": "D3",
                "type": "TO_REMOVE",
                # ~ 40m
                "latLngs": [
                    {"lat": 43.694364, "lng": 3.615415},
                    {"lat": 43.694094, "lng": 3.615085},
                ],
                "additionalData": {
                    "type_haie": "alignement",
                    "mode_destruction": "arrachage",
                },
            },
            {
                "id": "D4",
                "type": "TO_REMOVE",
                # ~ 30m
                "latLngs": [
                    {"lat": 43.694347, "lng": 3.615455},
                    {"lat": 43.694144, "lng": 3.615210},
                ],
                "additionalData": {
                    "type_haie": "arbustive",
                    "mode_destruction": "arrachage",
                },
            },
            {
                "id": "D5",
                "type": "TO_REMOVE",
                # ~ 20m
                "latLngs": [
                    {"lat": 43.694328, "lng": 3.615493},
                    {"lat": 43.694192, "lng": 3.615332},
                ],
                "additionalData": {
                    "type_haie": "buissonnante",
                    "mode_destruction": "arrachage",
                },
            },
            {
                "id": "D6",
                "type": "TO_REMOVE",
                # ~ 10m
                "latLngs": [
                    {"lat": 43.694305, "lng": 3.615543},
                    {"lat": 43.694235, "lng": 3.615464},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "mode_destruction": "arrachage",
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                },
            },
            {
                "id": "P2",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                },
            },
            {
                "id": "P3",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                },
            },
            {
                "id": "P4",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                },
            },
            {
                "id": "P5",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "alignement",
                },
            },
            {
                "id": "P6",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "type_haie": "alignement",
                },
            },
        ]
    )
    return hedge_data


def test_calvados_quality_condition(hedge_data):
    """Lengths to plant depends on R."""
    catalog = {
        "reimplantation": "remplacement",
        "LD": {
            "mixte": 100.0,
            "alignement": 40.0,
            "arbustive": 30.0,
            "buissonnante": 20.0,
            "degradee": 10.0,
        },
        "LC": {
            "mixte": 200.0,
            "alignement": 80.0,
            "arbustive": 60.0,
            "buissonnante": 40.0,
            "degradee": 10.0,
        },
        "lpm": 390.0,
        "reduced_lpm": 352.0,
    }
    R = 0.0  # Ignored for calvados
    condition = NormandieQualityCondition(hedge_data, R, catalog)
    condition.evaluate()
    LC = condition.context["LC"]

    assert round(LC["mixte"]) == 0
    assert round(LC["alignement"]) == 0
    assert round(LC["arbustive"]) == 60
    assert round(LC["buissonnante"]) == 40
    assert round(LC["degradee"]) == 10
