"""Tests for the MoulinetteHaie.get_criteria() method.

Covers scope-based filtering for both activation modes:
 - department_centroid: criterion included only if its scope has at least one hedge
 - hedges_intersection: geometry check uses only hedges of the criterion's scope
"""

import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_INSIDE,
    COORDS_BIZOUS_OUTSIDE,
    make_hedge,
    make_moulinette_haie_data,
)

EVALUATOR_HRU = "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieHru"
EVALUATOR_RU = "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieRu"
EVALUATOR_L3503 = "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieL3503"

# Hedge additionalData configs that produce each scope classification.
# In DC mode (non-single_procedure): all hedges → HRU.
# In RU mode (single_procedure): scope is computed per hedge.
HEDGE_RU = {
    "type_haie": "mixte"
}  # mixte hedge → RU (non-alignement, no exclusion props)
HEDGE_HRU = {"bord_batiment": True}  # excluded from RU → HRU
HEDGE_L3503 = {
    "type_haie": "alignement",
    "bord_voie": True,
}  # alignement + bord_voie → L350-3


@pytest.fixture
def urbanisme_regulation():
    return RegulationFactory(regulation="urbanisme_haie")


# ---------------------------------------------------------------------------
# department_centroid activation mode
# ---------------------------------------------------------------------------


def test_dc_hru_criterion_included_with_hru_hedges(france_map, urbanisme_regulation):
    """HRU criterion is returned when at least one HRU hedge exists (DC mode)."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_HRU,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    DCConfigHaieFactory()
    # In DC mode, all hedges are classified as HRU
    data = make_moulinette_haie_data(hedge_data=[make_hedge()])
    assert MoulinetteHaie(data).get_criteria().count() == 1


def test_dc_ru_criterion_excluded_in_dc_mode(france_map, urbanisme_regulation):
    """RU criterion is excluded in DC mode because no RU hedges exist."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_RU,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(hedge_data=[make_hedge()])
    assert MoulinetteHaie(data).get_criteria().count() == 0


def test_dc_ru_criterion_included_in_ru_mode_with_ru_hedge(
    france_map, urbanisme_regulation
):
    """RU criterion is returned in RU mode when at least one RU hedge exists."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_RU,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        reimplantation="remplacement", hedge_data=[make_hedge(**HEDGE_RU)]
    )
    assert MoulinetteHaie(data).get_criteria().count() == 1


def test_dc_ru_criterion_excluded_in_ru_mode_without_ru_hedge(
    france_map, urbanisme_regulation
):
    """RU criterion is excluded in RU mode when there are no RU hedges."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_RU,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(hedge_data=[make_hedge(**HEDGE_HRU)])
    assert MoulinetteHaie(data).get_criteria().count() == 0


def test_dc_l3503_criterion_included_with_l3503_hedge(france_map, urbanisme_regulation):
    """L350-3 criterion is returned in RU mode when a L350-3 hedge exists."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_L3503,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(hedge_data=[make_hedge(**HEDGE_L3503)])
    assert MoulinetteHaie(data).get_criteria().count() == 1


def test_dc_l3503_criterion_excluded_without_l3503_hedge(
    france_map, urbanisme_regulation
):
    """L350-3 criterion is excluded in RU mode when no L350-3 hedge exists."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_L3503,
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(hedge_data=[make_hedge(**HEDGE_RU)])
    assert MoulinetteHaie(data).get_criteria().count() == 0


# ---------------------------------------------------------------------------
# hedges_intersection activation mode
# ---------------------------------------------------------------------------


def test_intersection_hru_criterion_included_when_hru_hedge_intersects_zone(
    bizous_town_center, urbanisme_regulation
):
    """HRU criterion is returned when a HRU hedge intersects the activation zone."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_HRU,
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)]
    )
    assert MoulinetteHaie(data).get_criteria().count() == 1


def test_intersection_hru_criterion_excluded_when_hru_hedge_outside_zone(
    bizous_town_center, urbanisme_regulation
):
    """HRU criterion is excluded when HRU hedges do not intersect the activation zone."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_HRU,
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_OUTSIDE)]
    )
    assert MoulinetteHaie(data).get_criteria().count() == 0


def test_intersection_ru_criterion_included_when_ru_hedge_intersects_zone(
    bizous_town_center, urbanisme_regulation
):
    """RU criterion is returned when a RU hedge intersects the activation zone."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_RU,
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, **HEDGE_RU)]
    )
    assert MoulinetteHaie(data).get_criteria().count() == 1


def test_intersection_ru_criterion_excluded_when_only_hru_hedge_intersects_zone(
    bizous_town_center, urbanisme_regulation
):
    """RU criterion is excluded when only HRU hedges (not RU) intersect the zone."""
    CriterionFactory(
        regulation=urbanisme_regulation,
        evaluator=EVALUATOR_RU,
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    RUConfigHaieFactory()
    # bord_batiment=True → HRU hedge, not RU — even though it intersects the zone
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, **HEDGE_HRU)]
    )
    assert MoulinetteHaie(data).get_criteria().count() == 0
