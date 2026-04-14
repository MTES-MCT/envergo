import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory
from envergo.geodata.utils import trim_land


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
