"""Regression tests for the hedge density computation helpers.

Expected values are pinned as literal floats with tight tolerance.
Any drift beyond floating-point noise is a real regression.
"""

import pytest
from django.contrib.gis.geos import (
    GEOSGeometry,
    LineString,
    MultiLineString,
    Point,
    Polygon,
)

from envergo.geodata.tests.factories import (
    LineFactory,
    TerresEmergeesZoneFactory,
    map_lines,
)
from envergo.geodata.utils import (
    compute_hedge_densities_around_point,
    compute_hedge_density_around_lines,
    get_best_epsg_for_location,
    query_hedge_length,
    query_hedges_display_geojson,
)

pytestmark = [pytest.mark.django_db, pytest.mark.haie]

TEST_LNG = 3.58123
TEST_LAT = 49.32252


@pytest.fixture
def hedge_density_fixture():
    """One `density_reference` zone + one `haies` map with the default line."""
    LineFactory()
    TerresEmergeesZoneFactory()
    return Point(TEST_LNG, TEST_LAT, srid=4326)


EXPECTED_AROUND_POINT = {
    200: {"density": 0.0, "length": 0.0, "area_ha": 12.485780609039368},
    400: {
        "density": 20.04085317702949,
        "length": 1000.902783945812,
        "area_ha": 49.943122436167236,
    },
    5000: {
        "density": 1.2553400466934896,
        "length": 9796.187757968033,
        "area_ha": 7803.612880645973,
    },
}

EXPECTED_AROUND_LINES_400 = {
    "density": 12.015016118818387,
    "length": 9796.187757968033,
    "area_ha": 815.3287237480157,
}

APPROX = {"rel": 1e-9, "abs": 1e-9}


def test_density_around_point_pinned_values(hedge_density_fixture):
    """Per-radius density/length/area_ha must match pinned values.

    All radii are bundled in a single call — this is critical because
    the query uses the largest circle for row filtering and fast-path
    containment. A per-radius parameterized test would hide bugs where
    smaller radii get inflated by the larger circle's containment check.
    """
    bundle = compute_hedge_densities_around_point(
        hedge_density_fixture, radii=[200, 400, 5000]
    )

    for radius, expected in EXPECTED_AROUND_POINT.items():
        result = bundle[radius]
        assert result["density"] == pytest.approx(expected["density"], **APPROX)
        assert result["artifacts"]["length"] == pytest.approx(
            expected["length"], **APPROX
        )
        assert result["artifacts"]["area_ha"] == pytest.approx(
            expected["area_ha"], **APPROX
        )
        assert result["artifacts"]["truncated_circle"] is not None


def test_bundle_display_geojson(hedge_density_fixture):
    """Display geometry is a MultiLineString."""
    bundle = compute_hedge_densities_around_point(
        hedge_density_fixture,
        radii=[200, 400, 5000],
        include_display_geojson=True,
    )
    display = bundle["display_geojson"]
    assert display is not None
    assert display["type"] == "MultiLineString"
    assert len(display["coordinates"]) > 0


def test_bundle_off_land():
    """Off-land: sentinel values, but display geometry still populated."""
    LineFactory()
    p = Point(TEST_LNG, TEST_LAT, srid=4326)
    bundle = compute_hedge_densities_around_point(
        p,
        radii=[200, 400, 5000],
        include_display_geojson=True,
    )

    for r in [200, 400, 5000]:
        assert bundle[r]["density"] == 1.0
        assert bundle[r]["artifacts"]["length"] == 0
        assert bundle[r]["artifacts"]["area_ha"] == 0.0
        assert bundle[r]["artifacts"]["truncated_circle"] is None
        assert bundle[r]["artifacts"]["circle"] is not None

    display = bundle["display_geojson"]
    assert display is not None
    assert display["type"] == "MultiLineString"


def test_density_around_lines_pinned_values(hedge_density_fixture):
    """Lines variant: density/length/area_ha must match pinned values."""
    input_mls = map_lines.clone()
    input_mls.srid = 4326

    result = compute_hedge_density_around_lines(input_mls, 400)

    assert result["density"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["density"], **APPROX
    )
    assert result["artifacts"]["length"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["length"], **APPROX
    )
    assert result["artifacts"]["area_ha"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["area_ha"], **APPROX
    )
    assert result["artifacts"]["truncated_buffer_zone"] is not None


def test_query_hedge_length_excludes_forest_portion():
    """Hedge crossing a forest hole should only count the non-forest portion.

    The terres émergées map has holes for forest zones. A hedge fully inside
    the circle but partially crossing a forest hole should only count the
    portion outside the hole.

    Regression: the fast-path ST_CoveredBy check used the untruncated circle,
    so hedges fully inside the circle had their full length counted even when
    part of them fell in a forest hole.
    """
    # Straight horizontal hedge — easy to reason about when cut in half.
    hedge = MultiLineString(
        [LineString([(3.50, 49.32), (3.60, 49.32)])],
    )
    LineFactory(geometry=hedge)

    # Circle fully containing the hedge.
    outer = [
        (3.45, 49.30),
        (3.65, 49.30),
        (3.65, 49.35),
        (3.45, 49.35),
        (3.45, 49.30),
    ]
    circle = Polygon(outer, srid=4326)

    # Truncated buffer: same extent, with a forest hole over the eastern half.
    # The hole is inset from the outer ring to avoid shared edges (GEOS
    # TopologyException).
    forest = [
        (3.55, 49.305),
        (3.64, 49.305),
        (3.64, 49.345),
        (3.55, 49.345),
        (3.55, 49.305),
    ]
    truncated = Polygon(outer, forest, srid=4326)

    # Only the western half (3.50→3.55) counts: exactly ST_LengthSpheroid
    # on that segment.
    expected_length = 3635.0942003379914

    actual_length = query_hedge_length(truncated, circle)
    assert actual_length == pytest.approx(expected_length, **APPROX)


# Minimal real geometries from the production InternalError (5 km density
# circle near Calvados ∩ terres émergées). The truncated ring is invalid: its
# 4th and 7th vertices sit ~1e-8 apart — a near-zero-width spike — which GEOS
# can't node, so ST_Difference raises a non-noded TopologyException.
NON_NODED_CIRCLE = (
    "SRID=4326;POLYGON ((-0.6237620203873582 49.06185742287851, "
    "-0.6357821553197321 49.05794753296565, -0.648730704265775 49.05565240808752, "
    "-0.662111262251907 49.055060042435514, -0.675410983724087 49.05619316123933, "
    "-0.6881200843993746 49.059008353345156, -0.699751232308876 49.06339771918509, "
    "-0.7098581129920114 49.06919297386438, -0.66 49.2, -0.62 49.2, "
    "-0.6237620203873582 49.06185742287851))"
)
NON_NODED_TRUNCATED = (
    "SRID=4326;POLYGON ((-0.672361806552348 49.0580111626572, "
    "-0.682249967733818 49.057708064165034, -0.688120084399375 49.059008353345156, "
    "-0.688303859490724 49.05907770644035, -0.68926166513242 49.0725405043094, "
    "-0.689455522572321 49.075263660706895, -0.688303870234985 49.059077710495025, "
    "-0.672361806552348 49.0580111626572))"
)


@pytest.fixture
def non_noded_geometries():
    """Return (truncated_buffer, untruncated_circle) that crash ST_Difference."""
    circle = GEOSGeometry(NON_NODED_CIRCLE)
    truncated = GEOSGeometry(NON_NODED_TRUNCATED)
    return truncated, circle


def test_query_hedge_length_handles_non_noded_difference(non_noded_geometries):
    """Don't crash on an invalid truncated buffer.

    Regression for the ST_Difference excluded-zone optimization (commit
    750728481); fixed by wrapping both operands in ST_MakeValid.
    """
    truncated, circle = non_noded_geometries
    # A hedge inside the circle so the query processes a real row.
    LineFactory(
        geometry=MultiLineString([LineString([(-0.66, 49.06), (-0.661, 49.06)])])
    )

    length = query_hedge_length(truncated, circle)

    assert length >= 0.0


def test_query_hedges_display_geojson_handles_non_noded_difference(
    non_noded_geometries,
):
    """Same ST_Difference flaw, same fix, in the display query."""
    truncated, circle = non_noded_geometries
    LineFactory(
        geometry=MultiLineString([LineString([(-0.66, 49.06), (-0.661, 49.06)])])
    )

    # Returns without raising; result may be None when nothing intersects.
    query_hedges_display_geojson(truncated, circle)


# Land-trimmed buffer with a degenerate hole (first two vertices identical,
# only 2 distinct points). Captured from a real buffer — see trim_land.
DEGENERATE_HOLE_BUFFER = (
    "SRID=4326;POLYGON ((-0.90 48.95, -0.79 48.95, -0.79 49.06, "
    "-0.90 49.06, -0.90 48.95), "
    "(-0.873686783197342 48.97633255528753, "
    "-0.873686783197342 48.97633255528753, "
    "-0.873686783214866 48.9763325555225, "
    "-0.873686783197342 48.97633255528753))"
)

# Same outline without the hole, used as the raw circle.
DEGENERATE_HOLE_CIRCLE = (
    "SRID=4326;POLYGON ((-0.90 48.95, -0.79 48.95, -0.79 49.06, "
    "-0.90 49.06, -0.90 48.95))"
)

# Straddles the circle's west edge at the hole's latitude, forcing
# the slow-path clip against the degenerate hole.
DEGENERATE_HOLE_HEDGE = MultiLineString(
    [LineString([(-0.92, 48.97633255528753), (-0.85, 48.97633255528753)])]
)

# ST_LengthSpheroid of the in-buffer portion (lon -0.90 to -0.85).
DEGENERATE_HOLE_EXPECTED_LENGTH = 3660.3227769668383


@pytest.fixture
def degenerate_hole_geometries():
    """Return (truncated_buffer, untruncated_circle); the buffer is invalid."""
    truncated = GEOSGeometry(DEGENERATE_HOLE_BUFFER)
    circle = GEOSGeometry(DEGENERATE_HOLE_CIRCLE)
    # These tests prove nothing if the buffer is accidentally valid.
    assert not truncated.valid
    return truncated, circle


def test_query_hedge_length_clips_buffer_with_degenerate_hole(
    degenerate_hole_geometries,
):
    """An invalid buffer must neither crash the query nor skew the clip."""
    truncated, circle = degenerate_hole_geometries
    LineFactory(geometry=DEGENERATE_HOLE_HEDGE)

    length = query_hedge_length(truncated, circle)

    assert length == pytest.approx(DEGENERATE_HOLE_EXPECTED_LENGTH, **APPROX)


def test_query_hedges_display_geojson_handles_buffer_with_degenerate_hole(
    degenerate_hole_geometries,
):
    """The display query runs the same clip and must survive the same buffer."""
    truncated, circle = degenerate_hole_geometries
    LineFactory(geometry=DEGENERATE_HOLE_HEDGE)

    display = query_hedges_display_geojson(truncated, circle)

    assert display is not None
    assert display["type"] == "MultiLineString"


@pytest.mark.parametrize(
    "lng,lat,expected_epsg",
    [
        (3.58, 43.6, 32631),  # Montpellier — UTM 31N
        (-61.5, 16.2, 32620),  # Guadeloupe — UTM 20N
        (55.5, -21.1, 32740),  # Réunion — UTM 40S (southern hemisphere → 327xx)
    ],
)
def test_get_best_epsg_for_location(lng, lat, expected_epsg):
    """Pick the correct UTM zone for any location.

    Every metric computation (area, density, buffers) projects into this zone,
    so the selection must be right mainland and overseas alike.
    """
    assert get_best_epsg_for_location(lng, lat) == expected_epsg
