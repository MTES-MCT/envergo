import pytest

from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.hedges.regulations import (
    MinLengthCondition,
    RUMinLengthCondition,
    RUQualityCondition,
    SafetyCondition,
)
from envergo.hedges.services import PlantationEvaluator
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.regulations.ep import EspecesProtegeesRegimeUnique
from envergo.moulinette.regulations.regime_unique_haie import RegimeUniqueHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import (
    make_hedge_factory,
    make_moulinette_haie_with_density,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
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
    DCConfigHaieFactory(regulations_available=["alignement_arbres", "natura2000_haie"])
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


def test_ep_dispense_excludes_conditions_from_result(ep_ru_criterion, ru_criterion):
    """When EP RU evaluates to 'dispense', its conditions must not exist at all.

    EP dispense means no derogation is needed, so EP-specific plantation
    conditions are irrelevant — they must not be created, not just hidden.
    Only RU's conditions should drive the overall result.
    """
    # GIVEN a régime unique department with both EP RU and RU active,
    # and a short hedge (8m <= l_bas=10m) that triggers EP dispense
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=8)],
        reimplantation="replantation",
    )

    # Sanity check: EP RU should be in dispense
    assert moulinette.ep.ep_regime_unique.result_code == "dispense"

    # WHEN the plantation evaluator runs
    evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
    evaluator.evaluate()

    # THEN no condition from the EP evaluator should be in the list at all
    ep_conditions = [
        c
        for c in evaluator.conditions
        if isinstance(c.criterion_evaluator, EspecesProtegeesRegimeUnique)
    ]
    assert ep_conditions == [], (
        f"EP dispense should produce zero conditions, but found: "
        f"{[c.label for c in ep_conditions]}"
    )

    # AND no EP condition should appear in invalid_conditions
    ep_invalid = [
        c
        for c in evaluator.invalid_conditions
        if c.criterion_evaluator
        and isinstance(c.criterion_evaluator, EspecesProtegeesRegimeUnique)
    ]
    assert ep_invalid == []

    # AND RU's MinLengthCondition should still be present
    ru_min_length = [
        c
        for c in evaluator.conditions
        if isinstance(c, MinLengthCondition)
        and isinstance(c.criterion_evaluator, RegimeUniqueHaie)
    ]
    assert len(ru_min_length) == 1


class TestConditionDeduplication:
    """Tests for condition deduplication when multiple evaluators share condition classes."""

    def test_global_conditions_are_deduplicated(self, ep_ru_criterion, ru_criterion):
        """When both RU and EPRU are active, global conditions contains one of each class."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        condition_types = [type(c) for c in evaluator.conditions]
        assert condition_types.count(RUMinLengthCondition) == 1
        assert condition_types.count(RUQualityCondition) == 1
        assert condition_types.count(SafetyCondition) == 1

    def test_strictest_condition_is_kept(self, ep_ru_criterion, ru_criterion):
        """The deduplicated condition comes from EPRU (stricter coefficients)."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )

        # Sanity check: EPRU should not be in dispense
        assert moulinette.ep.ep_regime_unique.result_code != "dispense"

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        min_length = next(
            c for c in evaluator.conditions if isinstance(c, RUMinLengthCondition)
        )
        assert isinstance(min_length.criterion_evaluator, EspecesProtegeesRegimeUnique)

    def test_all_conditions_contains_duplicates(self, ep_ru_criterion, ru_criterion):
        """all_conditions retains both evaluators' conditions (no deduplication)."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )
        assert moulinette.ep.ep_regime_unique.result_code != "dispense"

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        all_types = [type(c) for c in evaluator.all_conditions]
        assert all_types.count(RUMinLengthCondition) == 2
        assert all_types.count(RUQualityCondition) == 2
        assert all_types.count(SafetyCondition) == 2

    def test_find_condition_uses_all_conditions(self, ep_ru_criterion, ru_criterion):
        """find_condition can locate a specific evaluator's condition even after dedup."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )
        assert moulinette.ep.ep_regime_unique.result_code != "dispense"

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        ru_evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        ep_evaluator = moulinette.ep.ep_regime_unique.get_evaluator()

        ru_cond = evaluator.find_condition(RUMinLengthCondition, ru_evaluator)
        ep_cond = evaluator.find_condition(RUMinLengthCondition, ep_evaluator)

        assert ru_cond is not None
        assert ep_cond is not None
        assert ru_cond is not ep_cond
        assert isinstance(ru_cond.criterion_evaluator, RegimeUniqueHaie)
        assert isinstance(ep_cond.criterion_evaluator, EspecesProtegeesRegimeUnique)

    def test_ep_dispense_no_deduplication_needed(self, ep_ru_criterion, ru_criterion):
        """When EPRU is in dispense, only RU conditions exist — no duplicates."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=8)],
            reimplantation="replantation",
        )
        assert moulinette.ep.ep_regime_unique.result_code == "dispense"

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        all_types = [type(c) for c in evaluator.all_conditions]
        assert all_types.count(RUMinLengthCondition) == 1
        assert all_types.count(SafetyCondition) == 1

        # conditions and all_conditions should be identical
        assert evaluator.conditions == evaluator.all_conditions

    def test_to_json_returns_deduplicated(self, ep_ru_criterion, ru_criterion):
        """to_json serializes only the deduplicated conditions."""
        RUConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )
        assert moulinette.ep.ep_regime_unique.result_code != "dispense"

        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        json_data = evaluator.to_json()
        labels = [item["label"] for item in json_data]
        assert labels.count("Longueur de la haie plantée") == 1
        assert labels.count("Type de haie plantée") == 1
        assert labels.count("Sécurité") == 1
