import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.evaluations.models import RESULTS
from envergo.geodata.constants import EPSG_WGS84
from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.models import HedgeCategory, HedgeList
from envergo.hedges.tests.factories import HedgeFactory
from envergo.moulinette.models import CityHallSubmission, MoulinetteHaie
from envergo.moulinette.regulations.regime_unique_haie import (
    URGENCE_MOTIFS,
    compute_ru_compensation_ratio,
)
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
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRu",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_ru_criteria_in_ru_mode():
    """In RU mode with mixte + alignement hedges, RU→soumis."""
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="mixte"),
            make_hedge(hedge_id="D2", type_haie="alignement", bord_voie=True),
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.ru__regime_unique_haie.result_code == "soumis"


def test_hru_criterion_non_concerne_in_ru_mode():
    """HRU criterion returns non_concerne when both HRU and RU hedges exist."""
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="mixte"),
            make_hedge(hedge_id="D2", type_haie="buissonnante", bord_batiment=True),
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.ru__regime_unique_haie.result_code == "soumis"


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
            "non_disponible",
            "non_disponible",
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
    if type_haie == "mixte":
        criterion = moulinette.regime_unique_haie.ru__regime_unique_haie
        assert criterion.result_code == expected_result_code


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [
        ("mixte", "non_disponible"),
        ("alignement", "non_disponible"),
    ],
)
def test_moulinette_evaluation_outside_RU(type_haie, expected_result):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert moulinette.regime_unique_haie.criteria.count() == 0


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
        """Without zonage, always return the default config for every hedge."""
        settings = zone_settings(default=(50, 1.0, 1.1, 1.2, 1.3))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=False)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_id"] == "default" for info in zone_info.values())

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
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_id"] == "default" for info in zone_info.values())


class TestZoneResolution:
    """Tests for has_ru_zonage=True — per-hedge zone lookup with distance fallback."""

    def test_centroid_in_zone_uses_zone_config(self):
        """When the hedge centroid falls inside a zonage polygon, use that zone."""
        make_zonage_map("zone_A")
        settings = zone_settings(("zone_A", 50, 1.2, 1.4, 1.6, 1.8))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_id"] == "zone_A" for info in zone_info.values())

    def test_centroid_not_in_zone_uses_nearest(self):
        """When no zone covers the hedge centroid, fall back to the nearest."""
        zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
        # Small polygon ~20 km from the HedgeFactory default centroid (~43.687, 3.585)
        nearby_poly = Polygon(
            (
                (3.58, 43.50),
                (3.59, 43.50),
                (3.59, 43.51),
                (3.58, 43.51),
                (3.58, 43.50),
            ),
            srid=EPSG_WGS84,
        )
        ZoneFactory(
            map=zonage_map,
            geometry=MultiPolygon([nearby_poly]),
            attributes={"identifiant_zone": "zone_nearest"},
        )
        settings = zone_settings(("zone_nearest", 50, 1.2, 1.4, 1.6, 1.8))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_id"] == "zone_nearest" for info in zone_info.values())

    def test_distant_zone_ignored(self):
        """A zone beyond the 50 km cap is ignored even if it's the nearest."""
        zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
        # Small polygon near Bordeaux (~350 km from HedgeFactory default centroid)
        distant_poly = Polygon(
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
            geometry=MultiPolygon([distant_poly]),
            attributes={"identifiant_zone": "zone_far"},
        )
        settings = zone_settings(("zone_far", 50, 1.2, 1.4, 1.6, 1.8))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_config"] is None for info in zone_info.values())

    def test_no_zones_returns_none(self):
        """When no zonage zones exist, zone config is None for every hedge."""
        settings = zone_settings(("zone_A", 50, 1.0, 1.0, 1.0, 1.0))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["zone_config"] is None for info in zone_info.values())

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
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        info = list(zone_info.values())[0]
        assert info["zone_id"] == "zone_unknown"
        assert info["zone_config"] is None

    def test_missing_zone_config_yields_non_disponible(self):
        """When zone config is None, the evaluator returns non_disponible."""
        settings = zone_settings(("zone_A", 50, 1.0, 1.0, 1.0, 1.0))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
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
        coefficients = moulinette.catalog["per_hedge_coefficients"]
        assert list(coefficients.values()) == [1.8]
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["high_density"] is True for info in zone_info.values())

    def test_arboree_low_density(self):
        """Mixte hedge + density below threshold → R4_arboree_LD."""
        settings = zone_settings(default=(60, 1.0, 1.1, 1.8, 2.0))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=40,
            hedges=[make_hedge_factory(length=100, type_haie="mixte")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["per_hedge_coefficients"]
        assert list(coefficients.values()) == [2.0]
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["high_density"] is False for info in zone_info.values())

    def test_non_arboree_high_density(self):
        """Non-mixte hedge + density above threshold → R1_non_arboree_HD."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[make_hedge_factory(length=100, type_haie="arbustive")],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["per_hedge_coefficients"]
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
        coefficients = moulinette.catalog["per_hedge_coefficients"]
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
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        assert all(info["high_density"] is True for info in zone_info.values())
        coefficients = moulinette.catalog["per_hedge_coefficients"]
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
        coefficients = moulinette.catalog["per_hedge_coefficients"]
        assert list(coefficients.values()) == [
            1.5
        ], f"{type_haie} should use R1_non_arboree_HD"

    def test_alignements_excluded_from_coefficients(self):
        """When all hedges are alignements, the RU evaluator is not loaded and
        compensation ratio is 0.0 (alignements are excluded from RU)."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)
        hedges = HedgeList([make_hedge_factory(length=100, type_haie="alignement")])
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=hedges,
            reimplantation="replantation",
        )
        assert compute_ru_compensation_ratio(moulinette, hedges) == 0.0


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
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
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
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
        # (100*2.0 + 100*1.0) / 200 = 1.5
        assert evaluator.get_replantation_coefficient() == 1.5

    def test_only_alignements_returns_zero(self):
        """When all hedges are alignements, ratio is 0.0."""
        settings = zone_settings(default=(60, 1.5, 1.7, 1.8, 2.1))
        RUConfigHaieFactory(single_procedure_settings=settings)

        hedges = HedgeList([make_hedge_factory(length=100, type_haie="alignement")])
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=hedges,
            reimplantation="replantation",
        )
        assert compute_ru_compensation_ratio(moulinette, hedges) == 0.0

    def test_outside_RU_returns_zero(self):
        """When not in régime unique, compensation ratio is 0.0."""
        DCConfigHaieFactory()
        hedges = HedgeList([make_hedge_factory(length=100, type_haie="mixte")])
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=hedges,
            reimplantation="replantation",
        )
        assert compute_ru_compensation_ratio(moulinette, hedges) == 0.0

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
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
        # zone_A, R3_arboree_HD = 4.0
        assert evaluator.get_replantation_coefficient() == 4.0


# ---------------------------------------------------------------------------
# Multi-zone tests — hedges in different zones get different coefficients
# ---------------------------------------------------------------------------

# Two non-overlapping zone polygons covering different areas of France.
# Zone A covers a southern area (lat ~43), zone B covers a northern area (lat ~44).
ZONE_A_POLY = Polygon(
    ((2.9, 42.9), (4.1, 42.9), (4.1, 43.8), (2.9, 43.8), (2.9, 42.9)),
    srid=EPSG_WGS84,
)
ZONE_B_POLY = Polygon(
    ((2.9, 43.9), (4.1, 43.9), (4.1, 44.8), (2.9, 44.8), (2.9, 43.9)),
    srid=EPSG_WGS84,
)


def make_two_zone_map(zone_a_id="zone_A", zone_b_id="zone_B"):
    """Create a zonage map with two non-overlapping zones."""
    zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
    ZoneFactory(
        map=zonage_map,
        geometry=MultiPolygon([ZONE_A_POLY]),
        attributes={"identifiant_zone": zone_a_id},
    )
    ZoneFactory(
        map=zonage_map,
        geometry=MultiPolygon([ZONE_B_POLY]),
        attributes={"identifiant_zone": zone_b_id},
    )
    return zonage_map


def make_hedge_at(lat, lng, length=100, type_haie="buissonnante"):
    """Create a HedgeFactory whose centroid is at the given coordinates.

    Both latLngs start identical; the ``length`` post-generation hook adjusts
    the endpoint so the hedge has the requested length while staying near the
    target point.
    """
    return HedgeFactory(
        latLngs=[{"lat": lat, "lng": lng}, {"lat": lat, "lng": lng}],
        length=length,
        additionalData__type_haie=type_haie,
        additionalData__sur_parcelle_pac=False,
    )


class TestMultiZoneHedges:
    """Tests for hedges located in different zones getting different coefficients."""

    def test_hedges_in_different_zones_get_different_coefficients(self):
        """Two hedges in two different zones get coefficients from their own zone."""
        make_two_zone_map()
        settings = zone_settings(
            ("zone_A", 60, 1.0, 1.1, 1.2, 1.3),
            ("zone_B", 60, 2.0, 2.1, 2.2, 2.3),
        )
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        hedge_south = make_hedge_at(lat=43.3, lng=3.5, type_haie="mixte")
        hedge_north = make_hedge_at(lat=44.3, lng=3.5, type_haie="mixte")
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[hedge_south, hedge_north],
            reimplantation="replantation",
        )
        coefficients = moulinette.catalog["per_hedge_coefficients"]
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        # Each hedge should be in its own zone
        assert zone_info[hedge_south.id]["zone_id"] == "zone_A"
        assert zone_info[hedge_north.id]["zone_id"] == "zone_B"
        # R3_arboree_HD from respective zones
        assert coefficients[hedge_south.id] == 1.2
        assert coefficients[hedge_north.id] == 2.2

    def test_same_density_different_threshold_different_hd_ld(self):
        """Same project density can be HD in one zone but LD in another."""
        make_two_zone_map()
        # Zone A: X_densite=50 (density 60 → HD), Zone B: X_densite=80 (density 60 → LD)
        settings = zone_settings(
            ("zone_A", 50, 1.0, 1.1, 1.2, 1.3),
            ("zone_B", 80, 2.0, 2.1, 2.2, 2.3),
        )
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        hedge_south = make_hedge_at(lat=43.3, lng=3.5, type_haie="arbustive")
        hedge_north = make_hedge_at(lat=44.3, lng=3.5, type_haie="arbustive")
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[hedge_south, hedge_north],
            reimplantation="replantation",
        )
        zone_info = moulinette.catalog["ru_per_hedge_zone_info"]
        coefficients = moulinette.catalog["per_hedge_coefficients"]
        # Zone A: density 60 >= X_densite 50 → HD → R1_non_arboree_HD=1.0
        assert zone_info[hedge_south.id]["high_density"] is True
        assert coefficients[hedge_south.id] == 1.0
        # Zone B: density 60 < X_densite 80 → LD → R2_non_arboree_LD=2.1
        assert zone_info[hedge_north.id]["high_density"] is False
        assert coefficients[hedge_north.id] == 2.1

    def test_one_hedge_without_zone_triggers_non_disponible(self):
        """When one hedge has no zone config, the evaluator returns non_disponible."""
        # Only create zone A (southern), no zone covering northern area
        zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
        ZoneFactory(
            map=zonage_map,
            geometry=MultiPolygon([ZONE_A_POLY]),
            attributes={"identifiant_zone": "zone_A"},
        )
        settings = zone_settings(("zone_A", 50, 1.0, 1.1, 1.2, 1.3))
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        hedge_south = make_hedge_at(lat=43.3, lng=3.5)
        # Hedge far from any zone (> 50 km away)
        hedge_far = make_hedge_at(lat=48.0, lng=3.5)
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[hedge_south, hedge_far],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
        assert evaluator.result_code == "non_disponible"

    def test_weighted_average_with_multi_zone_coefficients(self):
        """Weighted average correctly combines coefficients from different zones."""
        make_two_zone_map()
        settings = zone_settings(
            ("zone_A", 60, 1.0, 1.5, 2.0, 2.5),
            ("zone_B", 60, 3.0, 3.5, 4.0, 4.5),
        )
        RUConfigHaieFactory(single_procedure_settings=settings, has_ru_zonage=True)
        # 100m hedge in zone A (mixte, HD → R3=2.0)
        hedge_south = make_hedge_at(lat=43.3, lng=3.5, length=100, type_haie="mixte")
        # 100m hedge in zone B (mixte, HD → R3=4.0)
        hedge_north = make_hedge_at(lat=44.3, lng=3.5, length=100, type_haie="mixte")
        moulinette = make_moulinette_haie_with_density(
            density=80,
            hedges=[hedge_south, hedge_north],
            reimplantation="replantation",
        )
        evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
        # (100 * 2.0 + 100 * 4.0) / 200 = 3.0
        assert evaluator.get_replantation_coefficient() == 3.0


# ---------------------------------------------------------------------------
# Emergency procedure tests
# ---------------------------------------------------------------------------


class TestEmergencyProcedureForm:
    """Test the urgence complementary question visibility."""

    @pytest.mark.parametrize("motif", URGENCE_MOTIFS)
    def test_urgence_field_visible_for_trigger_motifs(self, motif):
        """The urgence question appears for each trigger motif in régime unique."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif=motif,
            urgence="oui",
        )
        moulinette = MoulinetteHaie(data)
        assert moulinette.catalog.get("urgence") == "oui"

    @pytest.mark.parametrize(
        "motif",
        [
            "amelioration_culture",
            "amenagement",
            "amelioration_ecologique",
            "embellissement",
        ],
    )
    def test_urgence_field_absent_for_non_trigger_motifs(self, motif):
        """The urgence question does not appear for motifs outside the trigger list."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif=motif,
            urgence="oui",
        )
        moulinette = MoulinetteHaie(data)
        assert "urgence" not in moulinette.catalog

    def test_urgence_field_absent_for_droit_constant(self):
        """The urgence question does not appear in droit constant mode."""
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif="securite",
            urgence="oui",
        )
        moulinette = MoulinetteHaie(data)
        assert "urgence" not in moulinette.catalog

    def test_urgence_in_additional_forms(self):
        """The urgence field appears in the additional forms for the user."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif="securite",
        )
        moulinette = MoulinetteHaie(data)
        field_names = [f.name for form in moulinette.additional_forms for f in form]
        assert "urgence" in field_names

    def test_urgence_not_in_additional_forms_droit_constant(self):
        """The urgence field does not appear in additional forms for droit constant."""
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif="securite",
        )
        moulinette = MoulinetteHaie(data)
        field_names = [f.name for form in moulinette.additional_forms for f in form]
        assert "urgence" not in field_names

    def test_urgence_not_in_additional_forms_wrong_motif(self):
        """The urgence field does not appear in additional forms for non-trigger motifs."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            motif="amenagement",
        )
        moulinette = MoulinetteHaie(data)
        field_names = [f.name for form in moulinette.additional_forms for f in form]
        assert "urgence" not in field_names


# ---------------------------------------------------------------------------
# results_by_category — per-category result at regulation and moulinette level
# ---------------------------------------------------------------------------


class TestResultsByCategory:
    """Test results_by_category at regulation and moulinette level."""

    def test_regulation_results_by_category_ru_mode(self):
        """In RU mode with mixte TO_REMOVE hedges, RU category is soumis."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        rbc = moulinette.regime_unique_haie.results_by_category
        assert rbc[HedgeCategory.hru] == RESULTS.non_disponible
        assert rbc[HedgeCategory.ru] == RESULTS.soumis
        assert rbc[HedgeCategory.l350_3] == RESULTS.non_disponible

    def test_regulation_results_by_category_dc_mode(self):
        """In DC mode, all categories are non_active."""
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        rbc = moulinette.regime_unique_haie.results_by_category
        assert rbc[HedgeCategory.hru] == RESULTS.non_disponible
        assert rbc[HedgeCategory.ru] == RESULTS.non_disponible
        assert rbc[HedgeCategory.l350_3] == RESULTS.non_disponible

    def test_regulation_results_non_activated(self):
        """A non-activated regulation returns non_active for all categories."""
        RUConfigHaieFactory(regulations_available=[])
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        rbc = moulinette.regime_unique_haie.results_by_category
        for category in HedgeCategory:
            assert rbc[category] == RESULTS.non_active

    def test_moulinette_results_by_category_aggregation(self):
        """MoulinetteHaie.results_by_category maps through GLOBAL_RESULT_MATRIX."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        rbc = moulinette.results_by_category
        assert rbc[HedgeCategory.ru] == "declaration"


# ---------------------------------------------------------------------------
# get_debug_context — hedges_and_category_by_type structure
# ---------------------------------------------------------------------------


class TestDebugContext:
    """Test MoulinetteHaie.get_debug_context returns hedges_and_category_by_type.

    The structure is {hedge_type: [(hedge, category), ...]} sorted by hedge ID.
    """

    def test_hedges_by_type_and_category_structure(self):
        """Debug context groups hedges by type (TO_REMOVE/TO_PLANT) then category."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(hedge_id="D1", hedge_type="TO_REMOVE", type_haie="mixte"),
                make_hedge(hedge_id="P1", hedge_type="TO_PLANT", type_haie="mixte"),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        ctx = moulinette.get_debug_context()
        htc = ctx["hedges_and_category_by_type"]
        assert "TO_REMOVE" in htc
        assert "TO_PLANT" in htc

    def test_hedges_assigned_to_correct_category(self):
        """TO_REMOVE mixte hedges go to RU category in RU mode."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(hedge_id="D1", hedge_type="TO_REMOVE", type_haie="mixte"),
                make_hedge(
                    hedge_id="D2", hedge_type="TO_REMOVE", type_haie="alignement"
                ),
                make_hedge(hedge_id="D3", hedge_type="TO_REMOVE", type_haie="mixte"),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        ctx = moulinette.get_debug_context()
        htc = ctx["hedges_and_category_by_type"]
        assert len(htc["TO_REMOVE"]) == 3
        assert htc["TO_REMOVE"][0][0].id == "D1"
        assert htc["TO_REMOVE"][1][0].id == "D2"
        assert htc["TO_REMOVE"][2][0].id == "D3"

    def test_dc_mode_all_hedges_in_hru(self):
        """In DC mode, all hedges go to HRU category."""
        DCConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(hedge_id="D1", hedge_type="TO_REMOVE", type_haie="mixte"),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        ctx = moulinette.get_debug_context()
        htc = ctx["hedges_and_category_by_type"]
        hru_remove = [h for h, c in htc["TO_REMOVE"] if c == HedgeCategory.hru]
        assert len(hru_remove) == 1

    def test_empty_hedges_returns_empty_categories(self):
        """Without haies in catalog, returns empty lists for all categories."""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        del moulinette.catalog["haies"]
        ctx = moulinette.get_debug_context()
        htc = ctx["hedges_and_category_by_type"]
        assert htc == {}


class TestCityHallSubmission:

    def test_projet_urba_returns_autorisation_urba(self):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
            contexte="projet-urba",
        )
        moulinette = MoulinetteHaie(data)
        assert moulinette.city_hall_submission == CityHallSubmission.AUTORISATION_URBA

    def test_ru_only_returns_none(self):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        assert HedgeCategory.ru in moulinette.results_by_category
        assert moulinette.city_hall_submission == CityHallSubmission.NONE

    def test_hru_only_returns_complete(self):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(type_haie="alignement", bord_voie=False),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        assert HedgeCategory.ru not in moulinette.results_by_category
        assert moulinette.city_hall_submission == CityHallSubmission.COMPLETE

    def test_ru_and_hru_returns_partial(self):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(hedge_id="D1", type_haie="mixte"),
                make_hedge(hedge_id="D2", type_haie="alignement", bord_voie=False),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        assert HedgeCategory.ru in moulinette.results_by_category
        assert len(moulinette.results_by_category) > 1
        assert moulinette.city_hall_submission == CityHallSubmission.PARTIAL
