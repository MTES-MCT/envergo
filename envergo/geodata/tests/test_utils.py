import pytest
from django.contrib.gis.geos import (
    GEOSGeometry,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import (
    LineFactory,
    MapFactory,
    TerresEmergeesZoneFactory,
    map_lines,
)
from envergo.geodata.utils import (
    compute_hedge_densities_around_point,
    compute_hedge_density_around_lines,
    query_hedge_length,
    query_hedges_display_geojson,
    trim_land,
)

pytestmark = [pytest.mark.django_db, pytest.mark.haie]


@pytest.fixture
def terres_emergees():
    """Deux zones séparées par un espace."""
    zone_west = Polygon(
        [
            (-2.0, 47.0),
            (-1.0, 47.0),
            (-1.0, 48.0),
            (-2.0, 48.0),
            (-2.0, 47.0),
        ]
    )
    zone_east = Polygon(
        [
            (1.0, 47.0),
            (2.0, 47.0),
            (2.0, 48.0),
            (1.0, 48.0),
            (1.0, 47.0),
        ]
    )
    return MapFactory(
        name="Terres émergées",
        map_type=MAP_TYPES.terres_emergees,
        zones__geometry=MultiPolygon([zone_west, zone_east]),
    )


@pytest.mark.django_db
def test_trim_land_no_intersection(terres_emergees):
    """Une géométrie entièrement en mer doit retourner None."""
    sea_polygon = MultiPolygon(
        [
            Polygon(
                [
                    (-0.5, 47.2),
                    (0.5, 47.2),
                    (0.5, 47.8),
                    (-0.5, 47.8),
                    (-0.5, 47.2),
                ]
            )
        ],
        srid=4326,
    )
    result = trim_land(sea_polygon)
    assert result is None


@pytest.mark.django_db
def test_trim_land_geometry_collection(terres_emergees):
    """Une géométrie qui chevauche une zone et touche le bord d'une autre.

    ST_Intersection peut retourner une GeometryCollection (polygone + ligne).
    ST_CollectionExtract(..., 3) ne garde que les polygones.
    """
    # Ce polygone chevauche zone_west et touche le bord de zone_east à x=1.0,
    # ce qui produit une GeometryCollection(Polygon, LineString)
    touching_polygon = MultiPolygon(
        [
            Polygon(
                [
                    (-1.5, 47.2),
                    (1.0, 47.2),
                    (1.0, 47.8),
                    (-1.5, 47.8),
                    (-1.5, 47.2),
                ]
            )
        ],
        srid=4326,
    )
    result = trim_land(touching_polygon)
    assert result is not None
    # Le résultat doit être un polygone, pas une LineString
    assert (
        "Polygon" in result.geom_type
    ), f"Attendu un Polygon, obtenu {result.geom_type}"


@pytest.mark.django_db
def test_trim_land_spans_two_zones(terres_emergees):
    """Une géométrie qui chevauche les deux zones terrestres.

    ST_CollectionExtract(..., 3) retourne un MultiPolygon contenant
    les deux intersections.
    """
    wide_polygon = MultiPolygon(
        [
            Polygon(
                [
                    (-1.5, 47.2),
                    (1.5, 47.2),
                    (1.5, 47.8),
                    (-1.5, 47.8),
                    (-1.5, 47.2),
                ]
            )
        ],
        srid=4326,
    )
    result = trim_land(wide_polygon)
    assert result is not None
    assert (
        result.geom_type == "MultiPolygon"
    ), f"Attendu MultiPolygon, obtenu {result.geom_type}"
    assert len(result) == 2, f"Attendu 2 polygones, obtenu {len(result)}"
    point_west = Point(-1.4, 47.5, srid=4326)
    point_east = Point(1.4, 47.5, srid=4326)
    assert result.contains(point_west), "Intersection ouest manquante"
    assert result.contains(point_east), "Intersection est manquante"


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
