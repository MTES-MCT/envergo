import pytest

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)


@pytest.fixture(autouse=True)
def alignementarbres_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="alignement_arbres")

    criteria = [
        CriterionFactory(
            title="Alignement arbres > L350-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(type_haie, bord_voie, motif):
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0695, "lng": 0.4420},
                ],
                "additionalData": {
                    "type_haie": type_haie,
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
                    "connexion_boisement": False,
                    "bord_voie": bord_voie,
                },
            }
        ]
    )
    data = {
        "motif": motif,
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": "44",
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize(
    "type_haie, bord_voie, motif, expected_result_code, expected_result, expected_r",
    [
        ("alignement", True, "securite", "soumis_securite", "soumis_declaration", 1.0),
        (
            "alignement",
            True,
            "embellissement",
            "soumis_esthetique",
            "soumis_declaration",
            1.0,
        ),
        (
            "alignement",
            True,
            "amelioration_culture",
            "soumis_autorisation",
            "soumis_autorisation",
            2.0,
        ),
        ("mixte", True, "amelioration_culture", "non_soumis", "non_soumis", 0.0),
        ("alignement", False, "amelioration_culture", "non_soumis", "non_soumis", 0.0),
    ],
)
def test_moulinette_evaluation(
    moulinette_data, expected_result_code, expected_result, expected_r
):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.alignement_arbres.result == expected_result
    assert (
        moulinette.alignement_arbres.alignement_arbres.result_code
        == expected_result_code
    )
    assert (
        moulinette.alignement_arbres.alignement_arbres.get_evaluator().get_replantation_coefficient()
        == expected_r
    )
