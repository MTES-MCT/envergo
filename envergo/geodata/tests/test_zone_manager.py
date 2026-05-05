import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.tests.factories import MapFactory, ZoneFactory

pytestmark = pytest.mark.django_db

EPSG_WGS84 = 4326

# Two non-overlapping rectangles in southern France.
ZONE_A_POLY = Polygon(
    ((2.9, 42.9), (4.1, 42.9), (4.1, 43.8), (2.9, 43.8), (2.9, 42.9)),
    srid=EPSG_WGS84,
)
ZONE_B_POLY = Polygon(
    ((2.9, 43.9), (4.1, 43.9), (4.1, 44.8), (2.9, 44.8), (2.9, 43.9)),
    srid=EPSG_WGS84,
)

# A point inside zone A, one inside zone B, and one outside both.
POINT_IN_A = Point(3.5, 43.3, srid=EPSG_WGS84)
POINT_IN_B = Point(3.5, 44.3, srid=EPSG_WGS84)
POINT_OUTSIDE = Point(10.0, 60.0, srid=EPSG_WGS84)


def make_zonage_map(zones, dept_code="44"):
    """Create a zonage Map with the given zone geometries and attributes.

    ``zones`` is a list of ``(MultiPolygon, attributes_dict)`` tuples.
    """
    zonage_map = MapFactory(
        map_type=MAP_TYPES.zonage, departments=[dept_code], zones=[]
    )
    created = []
    for geometry, attributes in zones:
        zone = ZoneFactory(map=zonage_map, geometry=geometry, attributes=attributes)
        created.append(zone)
    return created


class TestFindCovering:
    """Tests for Zone.objects.find_covering()."""

    def test_single_point_in_zone(self):
        """A point inside a zone is matched to that zone."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_covering({"p1": POINT_IN_A}, MAP_TYPES.zonage, "44")
        assert "p1" in result
        assert result["p1"].pk == zones[0].pk

    def test_multiple_points_in_different_zones(self):
        """Each point is matched to its own covering zone."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
                (MultiPolygon([ZONE_B_POLY]), {"identifiant_zone": "B"}),
            ]
        )
        result = Zone.objects.find_covering(
            {"p1": POINT_IN_A, "p2": POINT_IN_B}, MAP_TYPES.zonage, "44"
        )
        assert result["p1"].pk == zones[0].pk
        assert result["p2"].pk == zones[1].pk

    def test_point_outside_all_zones_is_absent(self):
        """A point outside all zones does not appear in the result."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_covering(
            {"p1": POINT_OUTSIDE}, MAP_TYPES.zonage, "44"
        )
        assert "p1" not in result

    def test_mixed_matched_and_unmatched(self):
        """Only matched points appear in the result dict."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_covering(
            {"inside": POINT_IN_A, "outside": POINT_OUTSIDE},
            MAP_TYPES.zonage,
            "44",
        )
        assert result["inside"].pk == zones[0].pk
        assert "outside" not in result

    def test_wrong_department_returns_empty(self):
        """Zones for a different department are not matched."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_covering({"p1": POINT_IN_A}, MAP_TYPES.zonage, "99")
        assert result == {}

    def test_wrong_map_type_returns_empty(self):
        """Zones of a different map type are not matched."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_covering(
            {"p1": POINT_IN_A}, MAP_TYPES.zone_sensible_ep, "44"
        )
        assert result == {}


class TestFindNearest:
    """Tests for Zone.objects.find_nearest()."""

    def test_point_inside_zone_returns_that_zone(self):
        """A point inside a zone is found as nearest (distance ~0)."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_nearest(POINT_IN_A, MAP_TYPES.zonage, "44", 50_000)
        assert result is not None
        assert result.pk == zones[0].pk

    def test_nearby_point_within_cap(self):
        """A point near (but outside) a zone is matched within the distance cap."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        # Just north of zone A's boundary (43.8), within 50 km.
        nearby = Point(3.5, 43.85, srid=EPSG_WGS84)
        result = Zone.objects.find_nearest(nearby, MAP_TYPES.zonage, "44", 50_000)
        assert result is not None
        assert result.pk == zones[0].pk

    def test_distant_point_beyond_cap_returns_none(self):
        """A point far beyond the distance cap returns None."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_nearest(
            POINT_OUTSIDE, MAP_TYPES.zonage, "44", 50_000
        )
        assert result is None

    def test_returns_closest_when_multiple_zones(self):
        """When multiple zones are within range, the closest one is returned."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
                (MultiPolygon([ZONE_B_POLY]), {"identifiant_zone": "B"}),
            ]
        )
        # Between the two zones but closer to B (43.8 < 43.88 < 43.9).
        between = Point(3.5, 43.88, srid=EPSG_WGS84)
        result = Zone.objects.find_nearest(between, MAP_TYPES.zonage, "44", 50_000)
        assert result is not None
        assert result.pk == zones[1].pk

    def test_wrong_department_returns_none(self):
        """Zones for a different department are not considered."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_nearest(POINT_IN_A, MAP_TYPES.zonage, "99", 50_000)
        assert result is None


class TestFindNearestBatch:
    """Tests for Zone.objects.find_nearest_batch()."""

    def test_single_unmatched_point(self):
        """A single point near a zone is matched."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        nearby = Point(3.5, 43.85, srid=EPSG_WGS84)
        result = Zone.objects.find_nearest_batch(
            {"p1": nearby}, MAP_TYPES.zonage, "44", 50_000
        )
        assert result["p1"].pk == zones[0].pk

    def test_multiple_points_matched_to_nearest(self):
        """Each point is matched to its closest zone."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
                (MultiPolygon([ZONE_B_POLY]), {"identifiant_zone": "B"}),
            ]
        )
        near_a = Point(3.5, 43.85, srid=EPSG_WGS84)
        near_b = Point(3.5, 44.85, srid=EPSG_WGS84)
        result = Zone.objects.find_nearest_batch(
            {"pa": near_a, "pb": near_b}, MAP_TYPES.zonage, "44", 50_000
        )
        assert result["pa"].pk == zones[0].pk
        assert result["pb"].pk == zones[1].pk

    def test_point_beyond_cap_is_absent(self):
        """A point beyond the distance cap does not appear in the result."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_nearest_batch(
            {"p1": POINT_OUTSIDE}, MAP_TYPES.zonage, "44", 50_000
        )
        assert "p1" not in result

    def test_empty_centroids_returns_empty(self):
        """An empty input dict returns an empty result."""
        make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        result = Zone.objects.find_nearest_batch({}, MAP_TYPES.zonage, "44", 50_000)
        assert result == {}

    def test_mixed_matched_and_unmatched(self):
        """Only points within range appear in the result."""
        zones = make_zonage_map(
            [
                (MultiPolygon([ZONE_A_POLY]), {"identifiant_zone": "A"}),
            ]
        )
        nearby = Point(3.5, 43.85, srid=EPSG_WGS84)
        result = Zone.objects.find_nearest_batch(
            {"near": nearby, "far": POINT_OUTSIDE},
            MAP_TYPES.zonage,
            "44",
            50_000,
        )
        assert result["near"].pk == zones[0].pk
        assert "far" not in result
