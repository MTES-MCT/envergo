from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.models import HedgeTypeBase
from envergo.hedges.regulations import NormandieQualityCondition
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.hedges.tests.helpers import (
    make_mock_hedge,
    make_mock_hedge_data,
    make_mock_evaluator,
)

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
    """Compensation with per-hedge coefficients and real hedge data.

    D1 (mixte ~50m, R=2), D2 (mixte ~50m, R=2), D3 (alignement ~40m, R=2),
    D4 (arbustive ~30m, R=2), D5 (buissonnante ~20m, R=2), D6 (degradee ~10m, R=1).
    Planted: P1-P4 are 4×~50m mixte, P5-P6 are 2×~50m alignement.
    Mixte and alignement deficits are fully compensated by planted mixte.
    Arbustive, buissonnante, and degradee deficits remain.
    """
    per_hedge_coefficients = {
        "D1": 2.0, "D2": 2.0, "D3": 2.0,
        "D4": 2.0, "D5": 2.0, "D6": 1.0,
    }
    catalog = {"per_hedge_coefficients": per_hedge_coefficients, "aggregated_r": 2.0}
    evaluator = Mock()
    evaluator.moulinette.config.single_procedure = False
    condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
    condition.evaluate()
    LC = condition.context["LC"]

    assert round(LC[HedgeTypeBase.MIXTE]) == 0
    assert round(LC[HedgeTypeBase.ALIGNEMENT]) == 0
    assert LC[HedgeTypeBase.ARBUSTIVE] > 0
    assert LC[HedgeTypeBase.BUISSONNANTE] > 0
    assert LC[HedgeTypeBase.DEGRADEE] > 0


def test_calvados_quality_condition_l350(hedge_data):
    """L350 result codes force condition to pass regardless of deficits."""
    per_hedge_coefficients = {"D1": 2.0, "D2": 2.0, "D3": 2.0, "D4": 2.0, "D5": 2.0, "D6": 1.0}
    catalog = {"per_hedge_coefficients": per_hedge_coefficients, "aggregated_r": 2.0}

    evaluator = Mock(result_code="dispense_L350")
    evaluator.moulinette.config.single_procedure = False
    condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
    condition.evaluate()
    assert condition.result

    evaluator = Mock(result_code="a_verifier_L350")
    evaluator.moulinette.config.single_procedure = False
    condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
    condition.evaluate()
    assert condition.result


def make_hedges_and_catalog(coefficients_by_type, aggregated_r=1.0):
    """Build mock hedges-to-remove and a catalog from desired per-type coefficients.

    ``coefficients_by_type`` maps hedge type to (length, coefficient) pairs.
    Returns (hedges_to_remove, catalog).
    """
    hedges = []
    per_hedge_coefficients = {}
    for hedge_type, (length, coeff) in coefficients_by_type.items():
        hedge = make_mock_hedge(hedge_type, length, hedge_id=f"{hedge_type}_h")
        hedges.append(hedge)
        if coeff > 0:
            per_hedge_coefficients[hedge.id] = coeff
    catalog = {
        "per_hedge_coefficients": per_hedge_coefficients,
        "aggregated_r": aggregated_r,
    }
    return hedges, catalog


# --- Comprehensive NormandieQualityCondition tests (public interface) ---


class TestNormandieQualityConditionCompensation:
    """Test the compensation algorithm through evaluate()."""

    def test_same_type_fills_deficit(self):
        """Same-type planted hedges fill deficit at rate 1.0."""
        to_remove, catalog = make_hedges_and_catalog({"mixte": (100, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 100)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_cross_type_with_rate_reduction(self):
        """Compensating with a higher type applies 0.8 rate (20% bonus).

        Need 80m arbustive. Plant 64m mixte → 64/0.8 = 80m effective.
        """
        to_remove, catalog = make_hedges_and_catalog({"arbustive": (80, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 64)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_cross_type_insufficient_at_reduced_rate(self):
        """63m mixte at 0.8 rate → 78.75m effective, not enough for 80m arbustive."""
        to_remove, catalog = make_hedges_and_catalog({"arbustive": (80, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 63)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert not condition.result

    def test_buissonnante_for_degradee_no_rate_reduction(self):
        """Buissonnante compensating degradee uses rate 1.0 (exception to 0.8 rule)."""
        to_remove, catalog = make_hedges_and_catalog({"degradee": (20, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("buissonnante", 20)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_buissonnante_for_degradee_insufficient_without_bonus(self):
        """16m buissonnante at rate 1.0 cannot fill 20m degradee deficit."""
        to_remove, catalog = make_hedges_and_catalog({"degradee": (20, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("buissonnante", 16)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert not condition.result
        assert condition.context["LC"][HedgeTypeBase.DEGRADEE] == 4

    def test_arbustive_for_degradee_with_rate_reduction(self):
        """Arbustive compensating degradee uses rate 0.8 (it's an upgrade).

        16m arbustive / 0.8 = 20m effective → fills 20m degradee.
        """
        to_remove, catalog = make_hedges_and_catalog({"degradee": (20, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("arbustive", 16)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_hint_shows_reduction_when_applicable(self):
        """Hint shows compensation reduction message when conditions are met.

        100m mixte hedge with R=2.0 → LC=200. Mixte gets no reduction,
        so lpm=reduced_lpm=200. But arbustive 50m with R=2.0 → LC=100,
        reduced to 80 (0.8). Total lpm=300, reduced=280.
        """
        to_remove, catalog = make_hedges_and_catalog(
            {"mixte": (100, 2.0), "arbustive": (50, 2.0)}, aggregated_r=2.0
        )
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 300)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 2.0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        hint = condition.hint
        assert "300" in hint
        assert "280" in hint

    def test_hint_no_reduction_when_lpm_equals_reduced(self):
        """Hint omits reduction message when lpm == reduced_lpm.

        Only mixte hedges → no 0.8 reduction applies.
        """
        to_remove, catalog = make_hedges_and_catalog(
            {"mixte": (100, 1.0)}, aggregated_r=1.0
        )
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 100)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 1.0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        hint = condition.hint
        assert "100" in hint
        assert "réduite" not in hint

    def test_text_lists_deficit_per_type(self):
        """When condition fails, text lists missing amounts for each type."""
        to_remove, catalog = make_hedges_and_catalog({
            "mixte": (10, 1.0),
            "alignement": (5, 1.0),
            "arbustive": (8, 1.0),
            "buissonnante": (12, 1.0),
            "degradee": (6, 1.0),
        })
        hedge_data = make_mock_hedge_data(to_remove=to_remove, to_plant=[])
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert not condition.result
        text = condition.text
        assert "10\xa0m de haie mixte" in text
        assert "5\xa0m de haie mixte ou d’alignement" in text
        assert "8\xa0m de haie arbustive ou mixte" in text
        assert "18\xa0m de haie buissonnante, arbustive ou mixte" in text

    def test_text_valid_when_passes(self):
        """When condition passes, text is the valid message."""
        to_remove, catalog = make_hedges_and_catalog({"mixte": (100, 1.0)})
        hedge_data = make_mock_hedge_data(
            to_remove=to_remove, to_plant=[make_mock_hedge("mixte", 100)]
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result
        assert "convient" in condition.text

    def test_l350_dispense_forces_pass(self):
        """L350 dispense result code forces condition to pass."""
        to_remove, catalog = make_hedges_and_catalog({"mixte": (100, 1.0)})
        hedge_data = make_mock_hedge_data(to_remove=to_remove, to_plant=[])
        evaluator = make_mock_evaluator(result_code="dispense_L350")
        condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
        condition.evaluate()
        assert condition.result

    def test_l350_a_verifier_forces_pass(self):
        """L350 a_verifier result code forces condition to pass."""
        to_remove, catalog = make_hedges_and_catalog({"mixte": (100, 1.0)})
        hedge_data = make_mock_hedge_data(to_remove=to_remove, to_plant=[])
        evaluator = make_mock_evaluator(result_code="a_verifier_L350")
        condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
        condition.evaluate()
        assert condition.result
