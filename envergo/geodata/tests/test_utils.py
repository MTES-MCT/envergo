import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

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
    """Display geometry is a MultiLineString when tolerance is set."""
    bundle = compute_hedge_densities_around_point(
        hedge_density_fixture,
        radii=[200, 400, 5000],
        display_simplify_tolerance=0.00005,
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
        display_simplify_tolerance=0.00005,
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
