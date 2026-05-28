"""Tests for the RUQualityCondition (régime unique EP).

Hedge lengths are approximate (geodesic computation), so pass/fail
assertions use a small buffer and numeric comparisons use pytest.approx.
"""

import pytest

from envergo.hedges.models import HedgeTypeBase
from envergo.hedges.regulations import RUQualityCondition
from envergo.hedges.tests.conftest import make_mock_evaluator as _make_mock_evaluator
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory

pytestmark = pytest.mark.django_db


def make_mock_evaluator(**kwargs):
    """Wrap shared helper with RU-specific defaults."""
    kwargs.setdefault("single_procedure", True)
    kwargs.setdefault("ep_bonus", 0.0)
    return _make_mock_evaluator(**kwargs)


class TestRUQualityConditionCompensation:
    """Test the RU quality compensation algorithm through evaluate()."""

    def test_exact_match_passes(self):
        """Planting the required amount of each type passes."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(additionalData__type_haie="arbustive", length=50, id="h2"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=205
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=105
                ),
            ]
        )
        coefficients = {"h1": 2.0, "h2": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result

    def test_insufficient_planting_fails(self):
        """Planting less than required fails with correct deficits."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=50
                ),
            ]
        )
        coefficients = {"h1": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert not condition.result
        assert condition.remaining[HedgeTypeBase.MIXTE] == pytest.approx(150, abs=1)

    def test_effective_coefficients_include_bonus(self):
        """Effective coefficients (raw + bonus) drive the compensation amount.

        Raw R = 2.0, bonus = 0.5 → effective R = 2.5 → need ~250m.
        The condition reads pre-computed effective coefficients.
        """
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="arbustive", length=100, id="h1"
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=255
                ),
            ]
        )
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients={"h1": 2.5}),
        )
        condition.evaluate()
        assert condition.result

    def test_effective_coefficients_insufficient(self):
        """Fails when effective coefficient pushes requirement beyond planted amount.

        Effective R = 2.5 → need ~250m, only 200m planted.
        """
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="arbustive", length=100, id="h1"
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=200
                ),
            ]
        )
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients={"h1": 2.5}),
        )
        condition.evaluate()
        assert not condition.result
        assert condition.remaining[HedgeTypeBase.ARBUSTIVE] == pytest.approx(50, abs=1)

    def test_buissonnante_deficit_filled_by_arbustive(self):
        """Arbustive substitutes for buissonnante at rate 1.0."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="buissonnante", length=100, id="h1"
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=155
                ),
            ]
        )
        coefficients = {"h1": 1.5}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result

    def test_buissonnante_deficit_filled_by_mixte(self):
        """Mixte substitutes for buissonnante at rate 1.0."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="buissonnante", length=100, id="h1"
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=155
                ),
            ]
        )
        coefficients = {"h1": 1.5}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result

    def test_arbustive_deficit_filled_by_mixte(self):
        """Mixte substitutes for arbustive at rate 1.0."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="arbustive", length=100, id="h1"
                ),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=205
                ),
            ]
        )
        coefficients = {"h1": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result

    def test_mixte_deficit_cannot_be_substituted(self):
        """No substitute exists for mixte — only mixte works."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="arbustive", length=300
                ),
            ]
        )
        coefficients = {"h1": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert not condition.result
        assert condition.remaining[HedgeTypeBase.MIXTE] == pytest.approx(200, abs=1)

    def test_alignement_hedges_excluded_from_lc(self):
        """Alignement hedges have no coefficient, so they don't appear in LC."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="alignement", length=100, id="aa1"
                ),
                HedgeFactory(additionalData__type_haie="mixte", length=50, id="h2"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=105
                ),
            ]
        )
        # Only h2 has a coefficient — aa1 is excluded
        coefficients = {"h2": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result
        assert HedgeTypeBase.ALIGNEMENT not in condition.remaining

    def test_different_coefficients_per_hedge(self):
        """Each hedge uses its own coefficient from the zone config."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h2"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=355
                ),
            ]
        )
        # h1 has R=1.5, h2 has R=2.0 → need ~150 + ~200 = ~350m
        coefficients = {"h1": 1.5, "h2": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert condition.result

    def test_different_coefficients_insufficient(self):
        """Fails when total planted is less than sum of per-hedge requirements."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h2"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=340
                ),
            ]
        )
        coefficients = {"h1": 1.5, "h2": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert not condition.result
        assert condition.remaining[HedgeTypeBase.MIXTE] > 0


class TestRUQualityConditionText:
    """Test deficit messages use RU terminology (arborée, not mixte)."""

    def test_text_valid_when_passes(self):
        """Passing condition shows the valid message."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
                HedgeFactory(
                    to_plant=True, additionalData__type_haie="mixte", length=105
                ),
            ]
        )
        coefficients = {"h1": 1.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert "convient" in condition.text

    def test_text_mixte_deficit_says_arboree(self):
        """Mixte deficit message uses 'arborée' (RU label)."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
            ]
        )
        coefficients = {"h1": 2.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert "de haie arborée" in condition.text

    def test_text_arbustive_deficit(self):
        """Arbustive deficit message mentions both arbustive and arborée."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="arbustive", length=100, id="h1"
                ),
            ]
        )
        coefficients = {"h1": 1.5}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert "de haie arbustive ou arborée" in condition.text

    def test_text_buissonnante_deficit(self):
        """Buissonnante deficit message lists all three acceptable types."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(
                    additionalData__type_haie="buissonnante", length=100, id="h1"
                ),
            ]
        )
        coefficients = {"h1": 1.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        assert "de haie buissonnante, arbustive ou arborée" in condition.text

    def test_text_multiple_deficits(self):
        """All deficit lines appear when all types have deficits."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=50, id="h1"),
                HedgeFactory(additionalData__type_haie="arbustive", length=30, id="h2"),
                HedgeFactory(
                    additionalData__type_haie="buissonnante", length=20, id="h3"
                ),
            ]
        )
        coefficients = {"h1": 1.0, "h2": 1.0, "h3": 1.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        condition.evaluate()
        text = condition.text
        assert "arborée" in text
        assert "arbustive ou arborée" in text
        assert "buissonnante, arbustive ou arborée" in text


class TestRUQualityConditionMustDisplay:
    """Test must_display behavior."""

    def test_must_display_when_hedges_to_compensate(self):
        """Displays when there are hedges with compensation requirements."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
            ]
        )
        coefficients = {"h1": 1.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(effective_coefficients=coefficients),
        )
        assert condition.must_display()

    def test_no_display_when_nothing_to_compensate(self):
        """Hidden when no hedges need compensation."""
        hedge_data = HedgeDataFactory(hedges=[])
        condition = RUQualityCondition(hedge_data, 0, make_mock_evaluator())
        assert not condition.must_display()

    def test_no_display_when_all_coefficients_zero(self):
        """Hidden when all per-hedge coefficients are zero (dispense)."""
        hedge_data = HedgeDataFactory(
            hedges=[
                HedgeFactory(additionalData__type_haie="mixte", length=100, id="h1"),
            ]
        )
        coefficients = {"h1": 0.0}
        condition = RUQualityCondition(
            hedge_data, 0, make_mock_evaluator(ep_bonus=0.0, effective_coefficients=coefficients),
        )
        assert not condition.must_display()
