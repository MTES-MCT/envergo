from math import ceil
from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.models import HedgeTypeBase
from envergo.hedges.regulations import (
    AisneQualityCondition,
    EssencesBocageresCondition,
    MinLengthCondition,
    PacParcelCondition,
    RUMinLengthCondition,
    RUQualityCondition,
    SafetyCondition,
    StrenghteningCondition,
    TreeAlignmentsCondition,
)
from envergo.hedges.tests.conftest import make_mock_evaluator
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.regulations.ep import EspecesProtegeesAisne
from envergo.moulinette.tests.factories import DCConfigHaieFactory, RUConfigHaieFactory
from envergo.moulinette.tests.utils import make_moulinette_haie_data

pytestmark = pytest.mark.django_db


@pytest.fixture
def ep_criterion_evaluator():
    DCConfigHaieFactory()
    data = make_moulinette_haie_data()
    moulinette = MoulinetteHaie(data)
    return EspecesProtegeesAisne(moulinette, 0, {})


@pytest.fixture
def ep_criterion_evaluator_ru():
    RUConfigHaieFactory()
    data = make_moulinette_haie_data()
    moulinette = MoulinetteHaie(data)
    return EspecesProtegeesAisne(moulinette, 0, {})


@pytest.fixture
def calvados_hedge_data():
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
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "interchamp": True,
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
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
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "interchamp": True,
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
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
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "interchamp": True,
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
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
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "interchamp": True,
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
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
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "interchamp": True,
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
                },
            },
        ]
    )
    return hedge_data


def test_minimum_length_condition(ep_criterion_evaluator):
    """Length to plant depends on the replantation coefficient."""

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0

    hedge_data.lineaire_detruit_pac.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 0

    condition = MinLengthCondition(hedge_data, 2.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 200

    condition = MinLengthCondition(hedge_data, 4.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 400


def test_minimum_length_pac_condition(ep_criterion_evaluator):
    """Length to plant on pac does not depends on R."""

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant_pac.return_value = []
    hedge_data.length_to_plant_pac.return_value = 0

    hedge_data.lineaire_detruit_pac.return_value = 100
    hedge_data.length_to_plant_pac.return_value = 0

    condition = PacParcelCondition(hedge_data, 2.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 100

    condition = PacParcelCondition(hedge_data, 4.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 100

    condition = PacParcelCondition(hedge_data, 0.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 0


def test_safety_condition(hedge_data, ep_criterion_evaluator):
    """Planting under power lines is not ok."""

    condition = SafetyCondition(hedge_data, 1.0, ep_criterion_evaluator)
    condition.evaluate()
    assert condition.result

    hedge_data.data[-1]["additionalData"].update(
        {
            "type_haie": "alignement",
            "sous_ligne_electrique": True,
        }
    )
    condition = SafetyCondition(hedge_data, 1.0, ep_criterion_evaluator)
    condition.evaluate()
    assert not condition.result


def test_quality_condition_amounts_to_compensate(hedge_data, ep_criterion_evaluator):
    """Amounts to compensate depend on R."""

    condition = AisneQualityCondition(hedge_data, 2.0, ep_criterion_evaluator)
    amounts = condition.get_amounts_to_compensate()
    assert round(amounts[HedgeTypeBase.DEGRADEE]) == 2 * 50
    assert round(amounts[HedgeTypeBase.BUISSONNANTE]) == 2 * 40
    assert round(amounts[HedgeTypeBase.ARBUSTIVE]) == 2 * 30
    assert round(amounts[HedgeTypeBase.MIXTE]) == 2 * 20
    assert round(amounts[HedgeTypeBase.ALIGNEMENT]) == 2 * 10

    condition = AisneQualityCondition(hedge_data, 4.0, ep_criterion_evaluator)
    amounts = condition.get_amounts_to_compensate()
    assert round(amounts[HedgeTypeBase.DEGRADEE]) == 4 * 50
    assert round(amounts[HedgeTypeBase.BUISSONNANTE]) == 4 * 40
    assert round(amounts[HedgeTypeBase.ARBUSTIVE]) == 4 * 30
    assert round(amounts[HedgeTypeBase.MIXTE]) == 4 * 20
    assert round(amounts[HedgeTypeBase.ALIGNEMENT]) == 4 * 10


def test_hedge_quality_should_be_sufficient(ep_criterion_evaluator):
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.lineaire_detruit_pac.return_value = 10
    hedge_data.length_to_plant_pac.return_value = 5

    condition = AisneQualityCondition(hedge_data, 2.0, ep_criterion_evaluator)
    condition.get_amounts_to_compensate = Mock(
        return_value={
            "degradee": 12,
            "buissonnante": 12,
            "arbustive": 16,
            "mixte": 18,
            "alignement": 20,
        }
    )
    condition.get_amounts_planted = Mock(
        return_value={
            "buissonnante": 24,
            "arbustive": 16,
            "mixte": 18,
            "alignement": 20,
        }
    )
    condition.evaluate()

    assert condition.result
    assert condition.context["missing_plantation"] == {
        HedgeTypeBase.MIXTE: 0,
        HedgeTypeBase.ALIGNEMENT: 0,
        HedgeTypeBase.ARBUSTIVE: 0,
        HedgeTypeBase.BUISSONNANTE: 0,
        HedgeTypeBase.DEGRADEE: 0,
    }


def test_hedge_quality_should_not_be_sufficient_dc(ep_criterion_evaluator):
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 5
    hedge_data.lineaire_detruit_pac.return_value = 10

    condition = AisneQualityCondition(hedge_data, 2.0, ep_criterion_evaluator)
    condition.get_amounts_to_compensate = Mock(
        return_value={
            HedgeTypeBase.DEGRADEE: 10,
            "buissonnante": 10,
            "arbustive": 10,
            "mixte": 10,
            "alignement": 10,
        }
    )
    condition.get_amounts_planted = Mock(
        return_value={
            HedgeTypeBase.BUISSONNANTE: 5,
            HedgeTypeBase.ARBUSTIVE: 5,
            HedgeTypeBase.MIXTE: 5,
            HedgeTypeBase.ALIGNEMENT: 5,
        }
    )
    condition.evaluate()
    assert not condition.result
    assert condition.context["missing_plantation"] == {
        HedgeTypeBase.MIXTE: 5,
        HedgeTypeBase.ALIGNEMENT: 5,
        HedgeTypeBase.ARBUSTIVE: 5,
        HedgeTypeBase.BUISSONNANTE: 5,
        HedgeTypeBase.DEGRADEE: 10,
    }


def test_hedge_quality_should_not_be_sufficient_ru(ep_criterion_evaluator_ru):
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 5
    hedge_data.lineaire_detruit_pac.return_value = 10

    condition = AisneQualityCondition(hedge_data, 2.0, ep_criterion_evaluator_ru)
    condition.get_amounts_to_compensate = Mock(
        return_value={
            "buissonnante": 10,
            "arbustive": 10,
            "mixte": 10,
            "alignement": 10,
        }
    )
    condition.get_amounts_planted = Mock(
        return_value={
            HedgeTypeBase.BUISSONNANTE: 5,
            HedgeTypeBase.ARBUSTIVE: 5,
            HedgeTypeBase.MIXTE: 5,
            HedgeTypeBase.ALIGNEMENT: 5,
        }
    )
    condition.evaluate()
    assert not condition.result
    assert condition.context["missing_plantation"] == {
        HedgeTypeBase.MIXTE: 5,
        HedgeTypeBase.ALIGNEMENT: 5,
        HedgeTypeBase.ARBUSTIVE: 5,
        HedgeTypeBase.BUISSONNANTE: 5,
    }


def test_strengthening_condition(calvados_hedge_data):
    hedge_data = calvados_hedge_data
    coefficients = {"D1": 1.0, "D2": 1.0, "D3": 1.0}
    catalog = {"reimplantation": "replantation"}
    evaluator = make_mock_evaluator(effective_coefficients=coefficients)

    condition = StrenghteningCondition(hedge_data, 1.0, evaluator, catalog)
    condition.evaluate()
    assert condition.result
    assert condition.context["strengthening_length"] == 0.0
    assert condition.context["missing_plantation_length"] < 0.0

    hedge_data.data[-1]["additionalData"]["mode_plantation"] = "renforcement"
    hedge_data.data[-2]["additionalData"]["mode_plantation"] = "reconnexion"

    condition = StrenghteningCondition(hedge_data, 1.0, evaluator, catalog)
    condition.evaluate()
    lpm = condition.compute_lpm()
    assert not condition.result
    assert condition.context["strengthening_length"] == 101.0
    assert condition.context["missing_plantation_length"] == ceil(0.8 * lpm)


def test_alignement_arbres_condition():
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
                    "mode_destruction": "arrachage",
                    "type_haie": "alignement",
                    "interchamp": True,
                    "bord_voie": True,
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
                    "mode_destruction": "arrachage",
                    "type_haie": "alignement",
                    "interchamp": True,
                    "bord_voie": True,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
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
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "interchamp": True,
                    "bord_voie": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
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
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "bord_voie": True,
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
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
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "bord_voie": True,
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
                },
            },
        ]
    )
    ep_criterion_evaluator = Mock(result_code="soumis_autorisation")
    catalog = {"reimplantation": "replantation"}

    condition = TreeAlignmentsCondition(
        hedge_data, 2.0, ep_criterion_evaluator, catalog
    )
    condition.evaluate()
    assert not condition.result
    assert condition.context["minimum_length_to_plant_aa_bord_voie"] == 180
    assert condition.context["aa_bord_voie_delta"] == 80

    ep_criterion_evaluator = Mock(result_code="soumis_esthetique")

    condition = TreeAlignmentsCondition(
        hedge_data, 1.0, ep_criterion_evaluator, catalog
    )
    condition.evaluate()
    assert condition.result
    assert condition.context["minimum_length_to_plant_aa_bord_voie"] == 90
    assert condition.context["aa_bord_voie_delta"] == 0.0


def test_essences_bocageres_condition(calvados_hedge_data, ep_criterion_evaluator):
    hedge_data = calvados_hedge_data
    catalog = {}
    condition = EssencesBocageresCondition(
        hedge_data, 1.0, ep_criterion_evaluator, catalog
    )
    condition.evaluate()
    assert condition.result

    hedge_data.data[-1]["additionalData"]["essences_non_bocageres"] = True
    condition = EssencesBocageresCondition(
        hedge_data, 1.0, ep_criterion_evaluator, catalog
    )
    condition.evaluate()
    assert not condition.result


# --- Comprehensive AisneQualityCondition tests (public interface) ---


class TestAisneQualityConditionSubstitution:
    """Test substitution rules through evaluate() without mocking internals."""

    def test_exact_match_passes(self):
        """Planted amounts matching minimum requirements exactly → pass."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
                HedgeFactory(additionalData__type_haie="arbustive", length=20),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=15
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=30
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert condition.result

    def test_alignement_deficit_filled_by_mixte(self):
        """Alignement deficit can be compensated by surplus mixte."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="alignement", length=20),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=30
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert condition.result

    def test_buissonnante_deficit_filled_by_arbustive(self):
        """Buissonnante deficit can be compensated by surplus arbustive."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="buissonnante", length=20),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=30
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert condition.result

    def test_degradee_deficit_filled_by_chain(self):
        """Degradee deficit can be filled by buissonnante, arbustive, or mixte."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="degradee", length=30),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="buissonnante", length=16
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=16
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=16
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert condition.result

    def test_arbustive_deficit_cannot_be_substituted(self):
        """No substitution exists for arbustive — must be matched exactly."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="arbustive", length=20),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=100
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert not condition.result

    def test_mixte_deficit_cannot_be_substituted(self):
        """No substitution exists for mixte — must be matched exactly."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=20),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=100
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert not condition.result

    def test_degradee_excluded_from_planted(self):
        """Planting degradee hedges does not count toward any compensation."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="degradee", length=10),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="degradee", length=100
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert not condition.result

    def test_r_coefficient_scales_minimum_lengths(self):
        """Higher R requires proportionally more planting per type."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=15
                ),
            ]
        )
        condition_ok = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition_ok.evaluate()
        assert condition_ok.result

        condition_fail = AisneQualityCondition(hedge_data, 2.0, make_mock_evaluator())
        condition_fail.evaluate()
        assert not condition_fail.result

    def test_must_display_false_when_nothing_to_compensate(self):
        """must_display returns False when there are no hedges to remove."""
        hedge_data = HedgeDataFactory(hedges=[])
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        assert not condition.must_display()

    def test_must_display_true_when_hedges_to_remove(self):
        """must_display returns True when there are hedges to remove."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        assert condition.must_display()

    def test_text_contains_deficit_messages(self):
        """When condition fails, text lists the missing amounts per type."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
                HedgeFactory(additionalData__type_haie="arbustive", length=10),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.0, make_mock_evaluator())
        condition.evaluate()
        assert not condition.result
        text = " ".join(condition.text.split())
        assert "de haie mixte" in text
        assert "arbustive" in text

    def test_text_valid_when_passes(self):
        """When condition passes, text is the valid message."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=15
                ),
            ]
        )
        condition = AisneQualityCondition(hedge_data, 1.5, make_mock_evaluator())
        condition.evaluate()
        assert condition.result
        assert "convient" in condition.text

    def test_single_procedure_uses_reduced_type_enum(self):
        """In single-procedure (RU) context, HedgeType enum excludes degradee."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=10),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=10
                ),
            ]
        )
        evaluator = make_mock_evaluator(single_procedure=True)
        condition = AisneQualityCondition(hedge_data, 1.0, evaluator)
        condition.evaluate()
        assert condition.result


class TestIsStricterThan:
    """Tests for the is_stricter_than / compare_strictness protocol."""

    def test_different_classes_raises_type_error(self):
        """Comparing different condition classes raises TypeError."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(length=100),
                HedgeFactory(to_plant=True, length=200),
            ]
        )
        evaluator = make_mock_evaluator(single_procedure=True)
        evaluator.get_replantation_coefficient.return_value = 1.0

        min_length = RUMinLengthCondition(hedge_data, 1.0, evaluator)
        min_length.evaluate()
        safety = SafetyCondition(hedge_data, 1.0, evaluator)
        safety.evaluate()

        with pytest.raises(TypeError):
            min_length.is_stricter_than(safety)

    def test_base_class_returns_false(self):
        """Non-overridden compare_strictness returns False (no deduplication)."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(length=100),
                HedgeFactory(to_plant=True, length=200),
            ]
        )
        evaluator = make_mock_evaluator(single_procedure=True)

        cond_a = MinLengthCondition(hedge_data, 1.0, evaluator)
        cond_a.evaluate()
        cond_b = MinLengthCondition(hedge_data, 1.0, evaluator)
        cond_b.evaluate()

        assert not cond_a.is_stricter_than(cond_b)
        assert not cond_b.is_stricter_than(cond_a)

    def test_ru_min_length_higher_requirement_is_stricter(self):
        """Higher local R produces a longer minimum — the stricter condition."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(length=100),
                HedgeFactory(to_plant=True, length=200),
            ]
        )
        evaluator_low = make_mock_evaluator(single_procedure=True)
        evaluator_low.get_replantation_coefficient.return_value = 1.0
        evaluator_high = make_mock_evaluator(single_procedure=True)
        evaluator_high.get_replantation_coefficient.return_value = 1.5

        cond_low = RUMinLengthCondition(hedge_data, 1.0, evaluator_low)
        cond_low.evaluate()
        cond_high = RUMinLengthCondition(hedge_data, 1.5, evaluator_high)
        cond_high.evaluate()

        assert cond_high.is_stricter_than(cond_low)
        assert not cond_low.is_stricter_than(cond_high)

    def test_ru_min_length_equal_requirement_neither_stricter(self):
        """Same R on both conditions — neither claims stricter."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(length=100),
                HedgeFactory(to_plant=True, length=200),
            ]
        )
        evaluator = make_mock_evaluator(single_procedure=True)
        evaluator.get_replantation_coefficient.return_value = 1.0

        cond_a = RUMinLengthCondition(hedge_data, 1.0, evaluator)
        cond_a.evaluate()
        cond_b = RUMinLengthCondition(hedge_data, 1.0, evaluator)
        cond_b.evaluate()

        assert not cond_a.is_stricter_than(cond_b)
        assert not cond_b.is_stricter_than(cond_a)

    def test_ru_quality_higher_lpm_is_stricter(self):
        """Higher per-hedge coefficients produce a larger LPm — the stricter condition."""
        to_remove = HedgeFactory(length=100, additionalData__type_haie="buissonnante")
        hedge_data = HedgeDataFactory(
            hedges=[
                to_remove,
                HedgeFactory(
                    to_plant=True,
                    length=200,
                    additionalData__type_haie="buissonnante",
                ),
            ]
        )
        hedge_id = to_remove.id
        evaluator_low = make_mock_evaluator(
            single_procedure=True,
            effective_coefficients={hedge_id: 1.0},
        )
        evaluator_high = make_mock_evaluator(
            single_procedure=True,
            effective_coefficients={hedge_id: 1.5},
        )

        cond_low = RUQualityCondition(hedge_data, 1.0, evaluator_low)
        cond_low.evaluate()
        cond_high = RUQualityCondition(hedge_data, 1.5, evaluator_high)
        cond_high.evaluate()

        assert cond_high.is_stricter_than(cond_low)
        assert not cond_low.is_stricter_than(cond_high)

    def test_safety_uses_base_behavior(self):
        """SafetyCondition is stateless — neither claims stricter, one is picked arbitrarily."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(length=100),
                HedgeFactory(to_plant=True, length=200),
            ]
        )
        evaluator_a = make_mock_evaluator(single_procedure=True)
        evaluator_b = make_mock_evaluator(single_procedure=True)

        cond_a = SafetyCondition(hedge_data, 1.0, evaluator_a)
        cond_a.evaluate()
        cond_b = SafetyCondition(hedge_data, 1.0, evaluator_b)
        cond_b.evaluate()

        assert not cond_a.is_stricter_than(cond_b)
        assert not cond_b.is_stricter_than(cond_a)
