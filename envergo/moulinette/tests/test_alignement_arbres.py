import pytest

from envergo.moulinette.models import MoulinetteHaie, Regulation
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
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
        (
            "mixte",
            True,
            "amelioration_culture",
            "non_disponible",
            "non_disponible",
            0.0,
        ),
        (
            "alignement",
            False,
            "amelioration_culture",
            "non_disponible",
            "non_disponible",
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

    if type_haie == "alignement" and bord_voie:
        criterion = moulinette.alignement_arbres.l350_3__alignement_arbres
        assert criterion.get_evaluator().get_replantation_coefficient() == expected_r
        assert criterion.result_code == expected_result_code


class TestCalvadosBeforeRu:
    @pytest.fixture(autouse=True)
    def calvados_criteria(self, france_map):
        regulation = Regulation.objects.get(regulation="alignement_arbres")
        CriterionFactory(
            title="Alignement arbres > L350-3 (Calvados avant RU)",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbresCalvadosBeforeRu",
            activation_map=france_map,
            activation_mode="department_centroid",
        )

    @pytest.mark.parametrize(
        "motif, expected_result_code",
        [
            ("securite", "soumis_securite"),
            ("embellissement", "soumis_esthetique"),
            ("amelioration_culture", "soumis_autorisation"),
            ("chemin_acces", "soumis_autorisation"),
            ("amenagement", "soumis_autorisation"),
        ],
    )
    def test_soumis_with_alignement_bord_voie(self, motif, expected_result_code):
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="alignement", bord_voie=True)],
            motif=motif,
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        criterion = moulinette.alignement_arbres.alignement_arbres_calvados_before_ru
        assert criterion.result_code == expected_result_code

    @pytest.mark.parametrize(
        "motif",
        ["securite", "amelioration_culture", "embellissement"],
    )
    def test_non_soumis_without_bord_voie(self, motif):
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="alignement", bord_voie=False)],
            motif=motif,
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        criterion = moulinette.alignement_arbres.alignement_arbres_calvados_before_ru
        assert criterion.result_code == "non_soumis"
