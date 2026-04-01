"""Tests for the EspecesProtegeesRegimeUnique evaluator."""

from unittest.mock import patch

import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, france_polygon
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data

DENSITY_PATCH = (
    "envergo.hedges.models.HedgeData.compute_density_around_lines_with_artifacts"
)


def _make_density_return(density):
    """Build a mock return value for compute_density_around_lines_with_artifacts."""
    return {
        "density": density,
        "artifacts": {
            "length": 3000,
            "area_ha": 50.0,
            "buffer_zone": None,
            "truncated_buffer_zone": None,
        },
    }


def _make_hedge_factory(length, type_haie="buissonnante", **extra):
    """Create a HedgeFactory with sur_parcelle_pac=False.

    The default HedgeFactory sets sur_parcelle_pac=True, which conflicts
    with localisation_pac="non" (the default in make_moulinette_haie_data)
    and causes the moulinette form to be invalid.
    """
    return HedgeFactory(
        length=length,
        additionalData__type_haie=type_haie,
        additionalData__sur_parcelle_pac=False,
        **extra,
    )


@pytest.fixture
def ep_ru_criterion(france_map):
    """Create an EP regulation with a single EspecesProtegeesRegimeUnique criterion."""
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="EP Régime Unique",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesRegimeUnique",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def regime_unique_haie_criterion(france_map):
    """Create the RU haie regulation needed for replantation coefficient."""
    regulation = RegulationFactory(regulation="regime_unique_haie")
    criteria = [
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaie",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def _build_moulinette(hedges, density, hedge_data=None):
    """Build a MoulinetteHaie with mocked density and correct form data.

    Pass either `hedges` (a HedgeData DB instance) or `hedge_data` (a list
    of dicts from make_hedge). Exactly one must be provided.
    """
    data = make_moulinette_haie_data(
        hedges=hedges,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    with patch(DENSITY_PATCH, return_value=_make_density_return(density)):
        moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    return moulinette


# ---------------------------------------------------------------------------
# Cascade algorithm — project-level rules
# ---------------------------------------------------------------------------


def test_ep_ru_aa_only(ep_ru_criterion):
    """All hedges are alignement → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="alignement"),
        make_hedge(hedge_id="D2", type_haie="alignement"),
    ]
    moulinette = _build_moulinette(None, density=60, hedge_data=hedge_data)
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_ripisylve_above_threshold(ep_ru_criterion):
    """Ripisylve length > 20m → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="buissonnante", ripisylve=True),
    ]
    moulinette = _build_moulinette(None, density=60, hedge_data=hedge_data)
    # Default hedge from COORDS_BIZOUS_INSIDE is ~25m (>20m threshold)
    assert moulinette.catalog["ep_ru_ripisylve_length"] > 20
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_short_total_dispense(ep_ru_criterion):
    """Total length <= 10m → dispense."""
    RUConfigHaieFactory()
    hedge = _make_hedge_factory(length=8)
    hedges = HedgeDataFactory(hedges=[hedge])
    moulinette = _build_moulinette(hedges, density=60)
    assert moulinette.catalog["ep_ru_total_length"] <= 10
    assert moulinette.ep.ep_regime_unique.result_code == "dispense"


def test_ep_ru_medium_total_moderate_density(ep_ru_criterion):
    """10m < total <= 100m and density < 80 → derogation_simplifiee."""
    RUConfigHaieFactory()
    hedge = _make_hedge_factory(length=50)
    hedges = HedgeDataFactory(hedges=[hedge])
    moulinette = _build_moulinette(hedges, density=60)
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_long_total_low_density(ep_ru_criterion):
    """Total > 100m and density < 50 → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge = _make_hedge_factory(length=120)
    hedges = HedgeDataFactory(hedges=[hedge])
    moulinette = _build_moulinette(hedges, density=40)
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


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
    hedge = _make_hedge_factory(length=120)
    hedges = HedgeDataFactory(hedges=[hedge])
    # density between D_BAS and D_HAUT so project-level rules don't short-circuit
    moulinette = _build_moulinette(hedges, density=65)
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_per_hedge_high_density_no_zone_sensible(ep_ru_criterion):
    """High density + no zone sensible → dispense via per-hedge."""
    RUConfigHaieFactory()
    hedge = _make_hedge_factory(length=120)
    hedges = HedgeDataFactory(hedges=[hedge])
    moulinette = _build_moulinette(hedges, density=90)
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique.result_code == "dispense"


def test_ep_ru_per_hedge_fallback_derogation_simplifiee(ep_ru_criterion):
    """Medium density, long total, no zone sensible → derogation_simplifiee."""
    RUConfigHaieFactory()
    hedge = _make_hedge_factory(length=120)
    hedges = HedgeDataFactory(hedges=[hedge])
    # density between D_BAS and D_HAUT, no zone sensible → fallback
    moulinette = _build_moulinette(hedges, density=65)
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_simplifiee"


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
    hedge = _make_hedge_factory(length=length)
    hedges = HedgeDataFactory(hedges=[hedge])
    moulinette = _build_moulinette(hedges, density=density)
    criterion = moulinette.ep.ep_regime_unique
    assert criterion.result_code == expected_code
    assert criterion.get_evaluator().get_replantation_coefficient() == expected_coeff
