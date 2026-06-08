from unittest.mock import PropertyMock, patch

import pytest

from envergo.evaluations.models import RESULTS
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa: F401
from envergo.hedges.models import HedgeCategory
from envergo.hedges.services import PlantationEvaluator, PlantationResults
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    PerimeterFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data

pytestmark = pytest.mark.django_db


@pytest.fixture
def regime_unique_haie_criteria(france_map):  # noqa: F811
    regulation = RegulationFactory(
        regulation="regime_unique_haie",
        evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRegulation",
    )
    return [
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRu",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]


@pytest.fixture
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


@pytest.fixture
def ep_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesSimple",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def n2000_criteria(france_map, bizous_town_center):  # noqa
    regulation = RegulationFactory(regulation="natura2000_haie", has_perimeters=True)

    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=france_map,
            activation_mode="hedges_intersection",
            evaluator_settings={"result": "soumis"},
        ),
    ]
    return criteria


def test_plantation_evaluator_should_evaluate_only_activated_regulations(
    ep_criteria, alignementarbres_criteria, n2000_criteria
):
    # GIVEN two regulations, one activated, one not activated, and one without activated perimeter on a department
    RUConfigHaieFactory(regulations_available=["alignement_arbres", "natura2000_haie"])
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
                    "type_haie": "alignement",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "ripisylve": False,
                    "connexion_boisement": False,
                    "bord_voie": True,
                },
            }
        ]
    )
    data = {
        "motif": "securite",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "contexte": "non",
        "element": "haie",
        "department": 44,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)

    # WHEN the plantation evaluator is created with these regulations
    evaluator = PlantationEvaluator(moulinette, moulinette_data["data"]["haies"])
    evaluator.evaluate()

    # THEN the plantation evaluator should only evaluate the activated regulation
    assert len(evaluator.conditions) == 2
    assert any(
        condition
        for condition in evaluator.conditions
        if condition.label == "Alignements d’arbres (L350-3)"
    )
    assert any(
        condition
        for condition in evaluator.conditions
        if condition.label == "Longueur de la haie plantée"
    )


class TestGlobalResultsByCategory:

    def test_combines_category_result_with_plantation_result(
        self, regime_unique_haie_criteria
    ):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        hedges = moulinette.catalog["haies"]
        evaluator = PlantationEvaluator(moulinette, hedges)
        evaluator.evaluate()

        # category_result="declaration" + plantation_result="inadequate" (no plantation hedges)
        # -> PLANTATION_RESULT_MATRIX maps to "inadequate"
        results = evaluator.global_results_by_category
        assert results[HedgeCategory.ru] == PlantationResults.Inadequate.value


class TestDisplayForAlternatives:

    def test_interdit_displays_for_alternatives(self, regime_unique_haie_criteria):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        hedges = moulinette.catalog["haies"]
        evaluator = PlantationEvaluator(moulinette, hedges)
        evaluator.evaluate()

        with patch.object(
            type(evaluator),
            "global_results_by_category",
            new_callable=PropertyMock,
            return_value={HedgeCategory.ru: RESULTS.interdit},
        ):
            assert evaluator.display_for_alternatives(HedgeCategory.ru) is True

    def test_non_soumis_does_not_display_for_alternatives(
        self, regime_unique_haie_criteria
    ):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        hedges = moulinette.catalog["haies"]
        evaluator = PlantationEvaluator(moulinette, hedges)
        evaluator.evaluate()

        with patch.object(
            type(evaluator),
            "global_results_by_category",
            new_callable=PropertyMock,
            return_value={HedgeCategory.ru: RESULTS.non_soumis},
        ):
            assert evaluator.display_for_alternatives(HedgeCategory.ru) is False
