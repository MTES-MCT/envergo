import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.geodata.tests.factories import MapFactory, ZoneFactory


@pytest.fixture
def france_map():
    """Fixture for a map containing mainland France territory."""

    map = MapFactory(name="France map", data_type="")

    # This is a rough pentagon that I manually drew on geoportail and that contains
    # France's mainland.
    pentagon = Polygon(
        [
            (2.239523057461999, 51.37848260569899),
            (-5.437949095065911, 48.830042871275225),
            (-2.020973593289057, 42.22052255703733),
            (7.672371135600932, 42.3263119734425),
            (9.759728555096416, 49.41947007260785),
            (2.239523057461999, 51.37848260569899),
        ]
    )
    ZoneFactory(map=map, geometry=MultiPolygon([pentagon]))

    return map


@pytest.fixture
def bizous_town_center():
    """A map with only Bizous's town center."""

    map = MapFactory(name="Bizou town center", data_type="")
    polygon = Polygon(
        [
            (0.4421436860179369, 43.06930871579473),
            (0.4421088173007432, 43.06925826047046),
            (0.44236765047068033, 43.069162248282396),
            (0.44240386029238143, 43.06922152113057),
            (0.4421436860179369, 43.06930871579473),
        ]
    )
    ZoneFactory(map=map, geometry=MultiPolygon([polygon]))
    return map
