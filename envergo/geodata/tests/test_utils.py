"""Semantic-equivalence regression tests for the hedge density helpers.

These tests pin the numerical output of `compute_hedge_density_around_point`
and `compute_hedge_density_around_lines` against a fixed fixture so that
upcoming refactors of the underlying SQL (multi-radius bundle query, faster
trim_land, etc.) can be validated as semantics-preserving.

Expected values were captured from the legacy implementation against the
fixture defined below. They are deliberately written as literal floats with
a tight tolerance — any drift bigger than floating-point noise is a real
regression and the implementation should be fixed, not the test.
"""

import pytest
from django.contrib.gis.geos import Point

from envergo.geodata.tests.factories import (
    LineFactory,
    TerresEmergeesZoneFactory,
    map_lines,
)
from envergo.geodata.utils import (
    compute_hedge_density_around_lines,
    compute_hedge_density_around_point,
)

pytestmark = [pytest.mark.django_db, pytest.mark.haie]


# Fixed test point inside both the default `LineFactory` line area
# (around lng~3.55, lat~49.33 — Limé, in northern France) and the
# `france_multipolygon` covering mainland France.
TEST_LNG = 3.58123
TEST_LAT = 49.32252


@pytest.fixture
def hedge_density_fixture():
    """Seed the test DB with one `terres_emergees` zone covering France
    and one `haies` map with the default `LineFactory` MultiLineString.
    """
    LineFactory()
    TerresEmergeesZoneFactory()
    return Point(TEST_LNG, TEST_LAT, srid=4326)


# Expected values captured from the legacy implementation against the
# fixture above. Pinned to lock in semantic equivalence across refactors.
EXPECTED_AROUND_POINT = {
    200: {
        "density": 0.0,
        "length": 0.0,
        "area_ha": 12.485780609039368,
    },
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


@pytest.mark.parametrize("radius", [200, 400, 5000])
def test_compute_hedge_density_around_point_semantic_equivalence(
    hedge_density_fixture, radius
):
    """Density/length/area_ha at each radius must match the pinned values.

    This is the regression net for any refactor that changes how the
    density math is computed (e.g. switching to a multi-radius bundle
    query, simplifying or reorganising trim_land, changing the cast/length
    pattern). If any of these literals drift, the implementation has
    regressed semantics and must be fixed before landing.
    """
    expected = EXPECTED_AROUND_POINT[radius]
    result = compute_hedge_density_around_point(hedge_density_fixture, radius)
    artifacts = result["artifacts"]

    assert result["density"] == pytest.approx(expected["density"], rel=1e-9, abs=1e-9)
    assert artifacts["length"] == pytest.approx(expected["length"], rel=1e-9, abs=1e-9)
    assert artifacts["area_ha"] == pytest.approx(expected["area_ha"], rel=1e-9, abs=1e-9)
    # truncated_circle is non-None for an on-land point with land coverage
    assert artifacts["truncated_circle"] is not None


# Expected values for the lines variant: a 400 m buffer around the
# `map_lines` MultiLineString, with the same `terres_emergees` zone and
# the same `LineFactory`-seeded haies map. The buffer encompasses the
# whole test line, so `length` matches the 5 km point variant above
# (both fully contain the test line).
EXPECTED_AROUND_LINES_400 = {
    "density": 12.015016118818387,
    "length": 9796.187757968033,
    "area_ha": 815.3287237480157,
}


def test_compute_hedge_density_around_lines_semantic_equivalence(
    hedge_density_fixture,
):
    """Density/length/area_ha for the 400 m buffer must match pinned values.

    Companion regression net for `compute_hedge_density_around_lines`.
    The fixture is the same as for the point variant; the input
    MultiLineString is the `map_lines` constant from the factories
    module — this is the same geometry the haies map was seeded with,
    so the function buffers it by 400 m and finds itself.
    """
    # Clone so we don't mutate the module-level constant when SRID is set.
    input_mls = map_lines.clone()
    input_mls.srid = 4326

    result = compute_hedge_density_around_lines(input_mls, 400)
    artifacts = result["artifacts"]

    assert result["density"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["density"], rel=1e-9, abs=1e-9
    )
    assert artifacts["length"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["length"], rel=1e-9, abs=1e-9
    )
    assert artifacts["area_ha"] == pytest.approx(
        EXPECTED_AROUND_LINES_400["area_ha"], rel=1e-9, abs=1e-9
    )
    assert artifacts["truncated_buffer_zone"] is not None
