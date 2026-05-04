"""Tests for the EspecesProtegeesRegimeUnique evaluator."""

import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, france_polygon
from envergo.moulinette.tests.factories import DCConfigHaieFactory, RUConfigHaieFactory
from envergo.moulinette.tests.utils import (
    EP_RU_DEFAULT_SETTINGS,
    make_hedge,
    make_hedge_factory,
    make_moulinette_haie_with_density,
    setup_ep_regime_unique,
    setup_regime_unique_haie,
)


@pytest.fixture
def ep_ru_criterion(france_map):
    """Create an EP regulation with a single EspecesProtegeesRegimeUnique criterion."""
    _regulation, criteria = setup_ep_regime_unique(france_map)
    return criteria


@pytest.fixture
def regime_unique_haie_criterion(france_map):
    """Create the RU haie regulation needed for replantation coefficient."""
    _regulation, criteria = setup_regime_unique_haie(france_map)
    return criteria


# ---------------------------------------------------------------------------
# Regime unique guard — step 0
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="Le critère EspecesProtegeesHorsRegimeUnique n'est pas encore spécifié"
)
def test_ep_ru_not_regime_unique_yields_non_concerne(ep_ru_criterion):
    """Department not in régime unique → non_concerne."""
    DCConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.ep.ep_regime_unique.result_code == "non_concerne"


# ---------------------------------------------------------------------------
# Cascade algorithm — project-level rules
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="Le critère EspecesProtegeesHorsRegimeUnique n'est pas encore spécifié"
)
def test_ep_ru_aa_only(ep_ru_criterion):
    """All hedges are alignement → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="alignement"),
        make_hedge(hedge_id="D2", type_haie="alignement"),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_lengths_exclude_alignements(ep_ru_criterion):
    """Lengths used in the cascade only count non-AA hedges."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="alignement"),
        make_hedge(hedge_id="D2", type_haie="buissonnante"),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    # Both hedges use the same default coordinates (~25m), so total_length
    # should reflect only the non-AA hedge, not both.
    total = moulinette.catalog["ep_ru_total_length"]
    assert total <= 30, (
        f"Expected length of a single hedge (~25m), got {total}. "
        "Alignement hedge should be excluded."
    )


def test_ep_ru_ripisylve_above_threshold(ep_ru_criterion):
    """Ripisylve length > 20m → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="buissonnante", ripisylve=True),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    # Default hedge from COORDS_BIZOUS_INSIDE is ~25m (>20m threshold)
    assert moulinette.catalog["ep_ru_ripisylve_length"] > 20
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_inventaire"


def test_ep_ru_short_total_dispense(ep_ru_criterion):
    """Total length <= 10m → dispense."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=8)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] <= 10
    assert moulinette.ep.ep_regime_unique__ru.result_code == "dispense"


def test_ep_ru_medium_total_moderate_density(ep_ru_criterion):
    """10m < total <= 100m and density < 80 → derogation_simplifiee."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_simplifiee"


def test_ep_ru_long_total_low_density(ep_ru_criterion):
    """Total > 100m and density < 50 → derogation_inventaire."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=40,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_inventaire"


# ---------------------------------------------------------------------------
# Cascade algorithm — per-hedge rules
# ---------------------------------------------------------------------------


def test_ep_ru_per_hedge_zone_sensible(ep_ru_criterion):
    """Long total + zone sensible hedge → derogation_inventaire via per-hedge."""
    RUConfigHaieFactory()
    MapFactory(
        name="Zone sensible EP",
        map_type=MAP_TYPES.zone_sensible_ep,
        zones__geometry=MultiPolygon([france_polygon]),
    )
    # density between D_BAS and D_HAUT so project-level rules don't short-circuit
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_inventaire"


def test_ep_ru_per_hedge_short_high_density_non_mixte_dispense(ep_ru_criterion):
    """Short total + high density + non-mixte + no zone → dispense via per-hedge.

    Reaches step 6 with total ∈ (L_BAS, L_HAUT] and density > D_HAUT, where
    the per-hedge dispense branch is exercised.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=50, type_haie="buissonnante")],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "dispense"


def test_ep_ru_per_hedge_short_high_density_mixte_no_dispense(ep_ru_criterion):
    """Short total + high density + mixte + no zone → derogation_simplifiee.

    Mixte hedges are excluded from the per-hedge dispense branch even when
    every other condition is met.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=50, type_haie="mixte")],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_long_high_density_no_dispense(ep_ru_criterion):
    """Long total + high density + no zone → derogation_simplifiee.

    Regression: long-total projects must NOT fall into the dispense branch,
    even with high density and no sensitive zone. The L_HAUT cap on the
    dispense path was missing in an earlier version of the spec.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_fallback_derogation_simplifiee(ep_ru_criterion):
    """Medium density, long total, no zone sensible → derogation_simplifiee."""
    RUConfigHaieFactory()
    # density between D_BAS and D_HAUT, no zone sensible → fallback
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_simplifiee"


# ---------------------------------------------------------------------------
# Replantation coefficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length, density, expected_code, expected_coeff",
    [
        (8, 60, "dispense", 1.5),  # R_ru=1.5 + bonus=0.0
        (50, 60, "derogation_simplifiee", 1.75),  # R_ru=1.5 + bonus=0.25
        (120, 40, "derogation_inventaire", 2.0),  # R_ru=1.5 + bonus=0.5
    ],
)
def test_ep_ru_replantation_coefficient(
    ep_ru_criterion,
    regime_unique_haie_criterion,
    length,
    density,
    expected_code,
    expected_coeff,
):
    """Replantation coefficient = R_ru + bonus per result level."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=density,
        hedges=[make_hedge_factory(length=length)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ep_regime_unique__ru
    assert criterion.result_code == expected_code
    assert criterion.get_evaluator().get_replantation_coefficient() == expected_coeff


# ---------------------------------------------------------------------------
# Settings form (admin-configurable thresholds)
# ---------------------------------------------------------------------------


def test_ep_ru_missing_settings_yields_non_disponible(france_map):
    """Empty evaluator_settings → criterion result is non_disponible."""
    setup_ep_regime_unique(france_map, evaluator_settings={})
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.ep.ep_regime_unique__ru.result_code == "non_disponible"


def test_ep_ru_settings_override_thresholds(france_map):
    """Overriding l_haut shifts a project from step 4 into step 6 territory.

    With the default l_haut=100, a 50 m project hits step 4
    (derogation_simplifiee). Lowering l_haut to 30 makes the same project
    "long", and combined with high density it falls into step 5
    (derogation_inventaire).
    """
    custom = dict(EP_RU_DEFAULT_SETTINGS, l_haut=30, d_bas=80)
    setup_ep_regime_unique(france_map, evaluator_settings=custom)
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 30
    assert moulinette.ep.ep_regime_unique__ru.result_code == "derogation_inventaire"
