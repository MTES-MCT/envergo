"""Regression tests for the hedge density computation helpers.

Expected values are pinned as literal floats with tight tolerance.
Any drift beyond floating-point noise is a real regression.
"""

import pytest
from django.contrib.gis.geos import LineString, MultiLineString, Point, Polygon

from envergo.geodata.tests.factories import (
    LineFactory,
    TerresEmergeesZoneFactory,
    map_lines,
)
from envergo.geodata.utils import (
    compute_hedge_densities_around_point,
    compute_hedge_density_around_lines,
    query_hedge_length,
)

pytestmark = [pytest.mark.django_db, pytest.mark.haie]

TEST_LNG = 3.58123
TEST_LAT = 49.32252


@pytest.fixture
def hedge_density_fixture():
    """One `terres_emergees` zone + one `haies` map with the default line."""
    LineFactory()
    TerresEmergeesZoneFactory()
    return Point(TEST_LNG, TEST_LAT, srid=4326)


EXPECTED_AROUND_POINT = {
    200: {"density": 0.0, "length": 0.0, "area_ha": 12.485780609039368},
    400: {
        "density": 20.041485812958307,
        "length": 1000.9343797592853,
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

    # Expected: only the western half (3.50→3.55) is counted.
    # Pinned from ST_LengthSpheroid on that segment.
    expected_length = 3635.0917235660813

    actual_length = query_hedge_length(truncated, circle)
    assert actual_length == pytest.approx(expected_length, **APPROX)
