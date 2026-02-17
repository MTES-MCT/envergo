import pytest

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)


@pytest.fixture(autouse=True)
def code_rural_criteria(request, france_map):  # noqa
    regulation = RegulationFactory(
        regulation="code_rural_haie",
        evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRuralHaieRegulation",
    )

    criteria = [
        CriterionFactory(
            title="Code rural L126-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRural",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data():
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.06930871579473, "lng": 0.4421436860179369},
                    {"lat": 43.069162248282396, "lng": 0.44236765047068033},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
                    "connexion_boisement": False,
                },
            }
        ]
    )
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": "44",
    }
    return {"initial": data, "data": data}


def test_moulinette_evaluation(moulinette_data):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.code_rural_haie.result == "a_verifier"

    assert moulinette.code_rural_haie.code_rural.result == "a_verifier"
