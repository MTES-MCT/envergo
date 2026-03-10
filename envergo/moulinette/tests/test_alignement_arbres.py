import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data


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
    type_haie, bord_voie, motif, expected_result_code, expected_result, expected_r
):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie, bord_voie=bord_voie)],
        motif=motif,
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.alignement_arbres.result == expected_result
    assert (
        moulinette.alignement_arbres.alignement_arbres.result_code
        == expected_result_code
    )
    assert (
        moulinette.alignement_arbres.alignement_arbres.get_evaluator().get_replantation_coefficient()
        == expected_r
    )
