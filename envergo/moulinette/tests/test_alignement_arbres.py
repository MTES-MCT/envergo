import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data


@pytest.fixture(autouse=True)
def alignementarbres_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="alignement_arbres")

    criteria = [
        CriterionFactory(
            title="Alignement arbres > L350-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbresL3503",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
        CriterionFactory(
            title="Alignement arbres > L350-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbresHru",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
        CriterionFactory(
            title="Alignement arbres > L350-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbresRu",
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
        ("mixte", True, "amelioration_culture", "non_concerne", "non_concerne", 0.0),
        (
            "alignement",
            False,
            "amelioration_culture",
            "non_concerne",
            "non_concerne",
            0.0,
        ),
    ],
)
def test_moulinette_evaluation(
    type_haie, bord_voie, motif, expected_result_code, expected_result, expected_r
):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie, bord_voie=bord_voie)],
        motif=motif,
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.alignement_arbres.result == expected_result

    if type_haie == "mixte":
        criterion = moulinette.alignement_arbres.ru__alignement_arbres
    elif not bord_voie:
        criterion = moulinette.alignement_arbres.hru__alignement_arbres
    else:
        criterion = moulinette.alignement_arbres.l350_3__alignement_arbres
        assert criterion.get_evaluator().get_replantation_coefficient() == expected_r

    assert criterion.result_code == expected_result_code
