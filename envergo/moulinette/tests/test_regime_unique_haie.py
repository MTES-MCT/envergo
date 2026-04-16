import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.geodata.utils import EPSG_WGS84
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import (
    make_hedge,
    make_hedge_factory,
    make_moulinette_haie_data,
    make_moulinette_haie_with_density,
)


@pytest.fixture(autouse=True)
def regime_unique_haie_criteria(request, france_map):  # noqa
    regulation = RegulationFactory(
        regulation="regime_unique_haie",
        evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRegulation",
    )
    if request.node.get_closest_marker("disable_regime_haie_criterion"):
        return

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


@pytest.mark.parametrize(
    "type_haie, expected_result, expected_result_code",
    [
        (
            "mixte",
            "soumis",
            "soumis",
        ),
        (
            "alignement",
            "non_concerne",
            "non_concerne_aa",
        ),
    ],
)
def test_moulinette_evaluation_single_procedure(
    type_haie, expected_result, expected_result_code
):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert (
        moulinette.regime_unique_haie.regime_unique_haie.result_code
        == expected_result_code
    )


@pytest.mark.parametrize(
    "type_haie, expected_result, expected_result_code",
    [
        ("mixte", "non_concerne", "non_concerne"),
        ("alignement", "non_concerne", "non_concerne"),
    ],
)
def test_moulinette_evaluation_droit_constant(
    type_haie, expected_result, expected_result_code
):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert (
        moulinette.regime_unique_haie.regime_unique_haie.result_code
        == expected_result_code
    )


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_active"), ("alignement", "non_active")],
)
def test_moulinette_evaluation_non_active(type_haie, expected_result):
    RUConfigHaieFactory(regulations_available=[])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_disponible"), ("alignement", "non_disponible")],
)
@pytest.mark.disable_regime_haie_criterion
def test_moulinette_evaluation_non_disponible(type_haie, expected_result):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result


# ---------------------------------------------------------------------------
# Zone-based coefficient tests
# ---------------------------------------------------------------------------


def make_zonage_map(zone_id, departments=None):
    """Create a zonage Map with a single Zone covering France."""
    if departments is None:
        departments = ["44"]
    zonage_map = MapFactory(
        map_type=MAP_TYPES.zonage,
        departments=departments,
        zones=[],
    )
    ZoneFactory(
        map=zonage_map,
        geometry=MultiPolygon([france_polygon]),
        attributes={"identifiant_zone": zone_id},
    )
    return zonage_map


def zone_settings(*zones, default=None):
    """Build a ``single_procedure_settings`` dict from zone configs.

    Each zone is a ``(key, X_densite, R1_non_arboree_HD, R2_non_arboree_LD,
    R3_arboree_HD, R4_arboree_LD)`` tuple. ``default`` follows the same
    5-value convention.
    """
    coeff = {}
    for key, dx, r1, r2, r3, r4 in zones:
        coeff[key] = {
            "X_densite": dx,
            "R1_non_arboree_HD": r1,
            "R2_non_arboree_LD": r2,
            "R3_arboree_HD": r3,
            "R4_arboree_LD": r4,
        }
    if default is not None:
        dx, r1, r2, r3, r4 = default
        coeff["default"] = {
            "X_densite": dx,
            "R1_non_arboree_HD": r1,
            "R2_non_arboree_LD": r2,
            "R3_arboree_HD": r3,
            "R4_arboree_LD": r4,
        }
    return {"coeff_compensation": coeff}


class TestNoZonage:
    """Tests for has_ru_zonage=False — always uses default, no zone lookup."""

    def test_uses_default_config(self):
        """Without zonage, always return the default config."""
        settings = zone_settings(default=(50, 1.0, 1.1, 1.2, 1.3))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=False)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] == "default"

    def test_ignores_existing_zonage_maps(self):
        """Zone maps exist but has_ru_zonage=False — they are not queried."""
        make_zonage_map("zone_A")
        settings = zone_settings(
            ("zone_A", 50, 3.0, 3.5, 4.0, 4.5),
            default=(50, 1.0, 1.0, 1.0, 1.0),
        )
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=False)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] == "default"


class TestZoneResolution:
    """Tests for has_ru_zonage=True — zone lookup with nearest-zone fallback."""

    def test_centroid_in_zone_uses_zone_config(self):
        """When the centroid falls inside a zonage polygon, use that zone's config."""
        make_zonage_map("zone_A")
        settings = zone_settings(("zone_A", 50, 1.2, 1.4, 1.6, 1.8))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] == "zone_A"

    def test_centroid_not_in_zone_uses_nearest(self):
        """When no zone covers the centroid, fall back to the nearest zone."""
        # Zone in dept 44 covers France → centroid is inside, so this would
        # match via covers. To test nearest-zone fallback, create a zone that
        # does NOT cover the centroid. Use a small polygon far from Nantes.
        zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
        # Small polygon near Bordeaux (~350 km from Nantes test hedges)
        small_poly = Polygon(
            (
                (-0.58, 44.83),
                (-0.57, 44.83),
                (-0.57, 44.84),
                (-0.58, 44.84),
                (-0.58, 44.83),
            ),
            srid=EPSG_WGS84,
        )
        ZoneFactory(
            map=zonage_map,
            geometry=MultiPolygon([small_poly]),
            attributes={"identifiant_zone": "zone_nearest"},
        )
        settings = zone_settings(("zone_nearest", 50, 1.2, 1.4, 1.6, 1.8))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] == "zone_nearest"

    def test_no_zones_returns_none(self):
        """When no zonage zones exist, zone config is None."""
        settings = zone_settings(("zone_A", 50, 1.0, 1.0, 1.0, 1.0))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] is None
        assert moulinette.catalog["ru_zone_config"] is None

    def test_zone_key_not_in_config_returns_none(self):
        """Zone found but its identifier has no matching config entry → None config."""
        make_zonage_map("zone_unknown")
        settings = zone_settings(("zone_X", 50, 2.0, 2.5, 3.0, 3.5))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_zone_id"] == "zone_unknown"
        assert moulinette.catalog["ru_zone_config"] is None

    def test_missing_zone_config_yields_non_disponible(self):
        """When zone config is None, the evaluator returns non_disponible."""
        settings = zone_settings(("zone_A", 50, 1.0, 1.0, 1.0, 1.0))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        assert evaluator.result_code == "non_disponible"


class TestPerHedgeCoefficients:
    """Test the density × hedge-type coefficient matrix."""

    def test_arboree_high_density(self):
        """Mixte hedge + density above threshold → R3_arboree_HD."""
        settings = zone_settings(default=(60, 1.0, 1.1, 1.8, 2.0))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [1.8]
        assert moulinette.catalog["ru_high_density"] is True

    def test_arboree_low_density(self):
        """Mixte hedge + density below threshold → R4_arboree_LD."""
        settings = zone_settings(default=(60, 1.0, 1.1, 1.8, 2.0))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=40,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [2.0]
        assert moulinette.catalog["ru_high_density"] is False

    def test_non_arboree_high_density(self):
        """Non-mixte hedge + density above threshold → R1_non_arboree_HD."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [1.5]

    def test_non_arboree_low_density(self):
        """Non-mixte hedge + density below threshold → R2_non_arboree_LD."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=40,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [1.7]

    def test_density_at_threshold_is_high(self):
        """Density exactly equal to X_densite counts as high density."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        assert moulinette.catalog["ru_high_density"] is True
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [1.8]

    @pytest.mark.parametrize("type_haie", ["buissonnante", "arbustive"])
    def test_all_non_mixte_types_are_non_arboree(self, type_haie):
        """buissonnante, arbustive map to non_arboree (degradee is not valid in RU)."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie=type_haie)],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert list(coefficients.values()) == [
            1.5
        ], f"{type_haie} should use R1_non_arboree_HD"

    def test_alignements_excluded_from_coefficients(self):
        """Alignement hedges should not appear in per-hedge coefficients."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="alignement")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["ru_per_hedge_coefficients"]
        assert coefficients == {}


class TestCompensationRatio:
    """Test the weighted-average aggregation of per-hedge coefficients."""

    def test_single_hedge_returns_its_coefficient(self):
        """A single non-alignement hedge → ratio equals its coefficient."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        assert evaluator.get_replantation_coefficient() == 1.8

    def test_weighted_average_mixed_types(self):
        """Multiple hedges of different types → weighted average by length."""
        # arboree_HD=2.0, non_arboree_HD=1.0
        settings = zone_settings(default=(60, 1.0, 1.5, 2.0, 2.5))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[
                make_hedge_factory(length=100, type_haie="mixte"),
                make_hedge_factory(length=100, type_haie="buissonnante"),
            ],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        # (100*2.0 + 100*1.0) / 200 = 1.5
        assert evaluator.get_replantation_coefficient() == 1.5

    def test_only_alignements_returns_zero(self):
        """When all hedges are alignements, ratio is 0.0."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="alignement")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        assert evaluator.get_replantation_coefficient() == 0.0

    def test_droit_constant_returns_zero(self):
        """When not in régime unique, ratio is 0.0."""
        DCConfigHaieFactory()
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        assert evaluator.get_replantation_coefficient() == 0.0

    def test_zone_specific_config_used_for_ratio(self):
        """When a zonage matches, its coefficients drive the ratio, not the default."""
        make_zonage_map("zone_A")
        settings = zone_settings(("zone_A", 50, 3.0, 3.5, 4.0, 4.5))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.regime_unique_haie.get_evaluator()
        # zone_A, R3_arboree_HD = 4.0
        assert evaluator.get_replantation_coefficient() == 4.0
