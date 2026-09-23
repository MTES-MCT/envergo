import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.geodata.tests.factories import DepartmentFactory, calvados_polygon
from envergo.hedges.services import PlantationEvaluator
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
            1.0,
        ),
        (
            "mixte",
            True,
            "amelioration_culture",
            "non_concerne",
            "non_concerne",
            0.0,
        ),
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

    if type_haie == "alignement" and bord_voie:
        criterion = moulinette.alignement_arbres.l350_3__alignement_arbres
        assert criterion.get_evaluator().get_replantation_coefficient() == expected_r
        assert criterion.result_code == expected_result_code


def test_replantation_coefficient_calvados_override():
    """Calvados keeps a 2.0 replantation coefficient for AA L350-3 autorisation."""
    department = DepartmentFactory(
        department="14", geometry=MultiPolygon([calvados_polygon])
    )
    RUConfigHaieFactory(department=department, l350_3_authorization_coefficient=2.0)
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="alignement", bord_voie=True)],
        motif="amelioration_culture",
        reimplantation="replantation",
        department="14",
    )
    moulinette = MoulinetteHaie(data)
    criterion = moulinette.alignement_arbres.l350_3__alignement_arbres
    assert criterion.get_evaluator().get_replantation_coefficient() == 2.0


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


class TestNonConcernedCategories:
    """L350-3 only concerns roadside tree alignments.

    Hedges of the `ru` and `hru` categories are never roadside tree alignments,
    so their evaluators always answer "non concerné", whatever the motif.
    """

    @pytest.mark.parametrize(
        "type_haie, bord_voie, criterion_slug",
        [
            ("mixte", False, "ru__alignement_arbres"),
            ("alignement", False, "hru__alignement_arbres"),
        ],
    )
    @pytest.mark.parametrize(
        "motif",
        ["securite", "embellissement", "amelioration_culture", "autre"],
    )
    def test_always_non_concerne(self, type_haie, bord_voie, criterion_slug, motif):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie=type_haie, bord_voie=bord_voie)],
            motif=motif,
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        criterion = getattr(moulinette.alignement_arbres, criterion_slug)

        assert criterion.result_code == "non_concerne"
        assert criterion.result == "non_concerne"

    @pytest.mark.parametrize(
        "type_haie, bord_voie, criterion_slug",
        [
            ("mixte", False, "ru__alignement_arbres"),
            ("alignement", False, "hru__alignement_arbres"),
        ],
    )
    def test_no_plantation_condition_at_all(self, type_haie, bord_voie, criterion_slug):
        """A regulation the project escapes must not constrain the plantation.

        These evaluators carry no PlantationConditionMixin, so they contribute
        no acceptability condition — neither the tree alignments one nor a
        zero-length minimum.
        """
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie=type_haie, bord_voie=bord_voie)],
            motif="amelioration_culture",
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        evaluator = getattr(
            moulinette.alignement_arbres, criterion_slug
        ).get_evaluator()

        assert not hasattr(evaluator, "plantation_evaluate")

        plantation = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        plantation.evaluate()
        assert [
            c for c in plantation.conditions if c.criterion_evaluator is evaluator
        ] == []
