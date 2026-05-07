from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.models import HedgeTypeBase
from envergo.hedges.regulations import NormandieQualityCondition
from envergo.hedges.tests.factories import HedgeDataFactory

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
    """Lengths to plant depends on R."""
    catalog = {
        "reimplantation": "remplacement",
        "LD": {
            "mixte": 100.0,
            "alignement": 40.0,
            "arbustive": 30.0,
            "buissonnante": 20.0,
            "degradee": 10.0,
        },
        "LC": {
            "mixte": 200.0,
            "alignement": 80.0,
            "arbustive": 60.0,
            "buissonnante": 40.0,
            "degradee": 10.0,
        },
        "lpm": 390.0,
        "reduced_lpm": 352.0,
    }
    evaluator = Mock()
    R = 0.0  # Ignored for calvados
    condition = NormandieQualityCondition(hedge_data, R, evaluator, catalog)
    condition.evaluate()
    LC = condition.context["LC"]

    assert round(LC[HedgeTypeBase.MIXTE]) == 0
    assert round(LC[HedgeTypeBase.ALIGNEMENT]) == 0
    assert round(LC[HedgeTypeBase.ARBUSTIVE]) == 60
    assert round(LC[HedgeTypeBase.BUISSONNANTE]) == 40
    assert round(LC[HedgeTypeBase.DEGRADEE]) == 10


def test_calvados_quality_condition_l350(hedge_data):
    """Lengths to plant depends on R."""
    catalog = {
        "reimplantation": "remplacement",
        "LD": {
            "mixte": 100.0,
            "alignement": 40.0,
            "arbustive": 30.0,
            "buissonnante": 20.0,
            "degradee": 10.0,
        },
        "LC": {
            "mixte": 0.0,
            "alignement": 0.0,
            "arbustive": 0.0,
            "buissonnante": 0.0,
            "degradee": 0.0,
        },
        "lpm": 390.0,
        "reduced_lpm": 352.0,
    }
    evaluator = Mock(result_code="dispense_L350")
    R = 0.0  # Ignored for calvados
    condition = NormandieQualityCondition(hedge_data, R, evaluator, catalog)
    condition.evaluate()

    assert condition.result

    evaluator = Mock(result_code="a_verifier_L350")
    condition = NormandieQualityCondition(hedge_data, R, evaluator, catalog)
    condition.evaluate()

    assert condition.result


# --- Helpers for lightweight mock-based tests ---


def make_mock_hedge(hedge_type, length):
    """Create a mock hedge with type and length."""
    h = Mock()
    h.hedge_type = hedge_type
    h.length = length
    return h


def make_mock_hedge_data(to_remove, to_plant):
    """Create a mock hedge data with hedges to remove and plant."""
    hd = Mock()
    hd.hedges_to_remove.return_value = to_remove
    hd.hedges_to_plant.return_value = to_plant
    return hd


def make_mock_evaluator(single_procedure=False, result_code="soumis"):
    """Create a mock criterion evaluator with the given context."""
    ev = Mock()
    ev.moulinette.config.single_procedure = single_procedure
    ev.result_code = result_code
    return ev


def make_lc(**overrides):
    """Build an LC dict with zeros, overridden by keyword args."""
    lc = {"mixte": 0, "alignement": 0, "arbustive": 0, "buissonnante": 0, "degradee": 0}
    lc.update(overrides)
    return lc


def make_catalog(lc, lpm=0, reduced_lpm=0, aggregated_r=1.0):
    """Build a catalog dict for NormandieQualityCondition."""
    return {"LC": lc, "lpm": lpm, "reduced_lpm": reduced_lpm, "aggregated_r": aggregated_r}


# --- Comprehensive NormandieQualityCondition tests (public interface) ---


class TestNormandieQualityConditionCompensation:
    """Test the compensation algorithm through evaluate()."""

    def test_same_type_fills_deficit(self):
        """Same-type planted hedges fill deficit at rate 1.0."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 100)]
        )
        catalog = make_catalog(make_lc(mixte=100), lpm=100, reduced_lpm=100)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_cross_type_with_rate_reduction(self):
        """Compensating with a higher type applies 0.8 rate (20% bonus).

        Need 80m arbustive. Plant 64m mixte → 64/0.8 = 80m effective.
        """
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 64)]
        )
        catalog = make_catalog(make_lc(arbustive=80), lpm=80, reduced_lpm=64)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_cross_type_insufficient_at_reduced_rate(self):
        """63m mixte at 0.8 rate → 78.75m effective, not enough for 80m arbustive."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 63)]
        )
        catalog = make_catalog(make_lc(arbustive=80), lpm=80, reduced_lpm=64)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert not condition.result

    def test_buissonnante_for_degradee_no_rate_reduction(self):
        """Buissonnante compensating degradee uses rate 1.0 (exception to 0.8 rule)."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("buissonnante", 20)]
        )
        catalog = make_catalog(make_lc(degradee=20), lpm=20, reduced_lpm=20)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_buissonnante_for_degradee_insufficient_without_bonus(self):
        """16m buissonnante at rate 1.0 cannot fill 20m degradee deficit."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("buissonnante", 16)]
        )
        catalog = make_catalog(make_lc(degradee=20), lpm=20, reduced_lpm=20)
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
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("arbustive", 16)]
        )
        catalog = make_catalog(make_lc(degradee=20), lpm=20, reduced_lpm=16)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result

    def test_hint_shows_reduction_when_applicable(self):
        """Hint shows compensation reduction message when conditions are met."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 200)]
        )
        catalog = make_catalog(
            make_lc(mixte=100), lpm=200, reduced_lpm=160, aggregated_r=2.0
        )
        condition = NormandieQualityCondition(
            hedge_data, 2.0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        hint = condition.hint
        assert "200\xa0m" in hint
        assert "160\xa0m" in hint

    def test_hint_no_reduction_when_lpm_equals_reduced(self):
        """Hint omits reduction message when lpm == reduced_lpm."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 100)]
        )
        catalog = make_catalog(
            make_lc(mixte=100), lpm=100, reduced_lpm=100, aggregated_r=1.0
        )
        condition = NormandieQualityCondition(
            hedge_data, 1.0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        hint = condition.hint
        assert "100\xa0m" in hint
        assert "réduite" not in hint

    def test_text_lists_deficit_per_type(self):
        """When condition fails, text lists missing amounts for each type."""
        hedge_data = make_mock_hedge_data(to_remove=[], to_plant=[])
        catalog = make_catalog(
            make_lc(mixte=10, alignement=5, arbustive=8, buissonnante=12, degradee=6)
        )
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert not condition.result
        text = condition.text
        assert "10\xa0m de haie mixte" in text
        assert "5\xa0m de haie mixte ou d'alignement" in text
        assert "8\xa0m de haie arbustive ou mixte" in text
        assert "18\xa0m de haie buissonnante, arbustive ou mixte" in text

    def test_text_valid_when_passes(self):
        """When condition passes, text is the valid message."""
        hedge_data = make_mock_hedge_data(
            to_remove=[], to_plant=[make_mock_hedge("mixte", 100)]
        )
        catalog = make_catalog(make_lc(mixte=100), lpm=100, reduced_lpm=100)
        condition = NormandieQualityCondition(
            hedge_data, 0, make_mock_evaluator(), catalog
        )
        condition.evaluate()
        assert condition.result
        assert "convient" in condition.text

    def test_l350_dispense_forces_pass(self):
        """L350 dispense result code forces condition to pass."""
        hedge_data = make_mock_hedge_data(to_remove=[], to_plant=[])
        catalog = make_catalog(make_lc(mixte=100), lpm=100, reduced_lpm=80)
        evaluator = make_mock_evaluator(result_code="dispense_L350")
        condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
        condition.evaluate()
        assert condition.result

    def test_l350_a_verifier_forces_pass(self):
        """L350 a_verifier result code forces condition to pass."""
        hedge_data = make_mock_hedge_data(to_remove=[], to_plant=[])
        catalog = make_catalog(make_lc(mixte=100), lpm=100, reduced_lpm=80)
        evaluator = make_mock_evaluator(result_code="a_verifier_L350")
        condition = NormandieQualityCondition(hedge_data, 0, evaluator, catalog)
        condition.evaluate()
        assert condition.result
