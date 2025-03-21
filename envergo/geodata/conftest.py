import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory, ZoneFactory

# This is a rough pentagon that I manually drew on geoportail and that contains
# France's mainland.
france_polygon = Polygon(
    [
        (2.239523057461999, 51.37848260569899),
        (-5.437949095065911, 48.830042871275225),
        (-2.020973593289057, 42.22052255703733),
        (7.672371135600932, 42.3263119734425),
        (9.759728555096416, 49.41947007260785),
        (2.239523057461999, 51.37848260569899),
    ]
)

# Very rough department outlines
loire_atlantique_polygon = Polygon(
    [
        (-2.318813217788111, 47.11172939002415),
        (-1.8093222509912361, 46.85878309487171),
        (-1.0224264990381111, 47.06497777827326),
        (-1.336910141616236, 47.267582403961455),
        (-0.8782309423974862, 47.364409358656644),
        (-1.272365463881861, 47.826525823757436),
        (-2.679988754897486, 47.46013043348137),
        (-2.550899399428736, 47.13508980827845),
        (-2.215816391616236, 47.213505682461204),
        (-2.318813217788111, 47.11172939002415),
    ]
)

herault_polygon = Polygon(
    [
        (3.215640301549349, 43.22794194612112),
        (2.5426723773152715, 43.395887014114464),
        (3.2656957338328425, 43.913967044500254),
        (3.841333590843401, 43.96202635483297),
        (4.262633800688122, 43.58351502379401),
        (3.215640301549349, 43.22794194612112),
    ]
)


@pytest.fixture
def france_map():
    """Fixture for a map containing mainland France territory."""

    map = MapFactory(
        name="France map",
        map_type="",
        zones=[ZoneFactory(geometry=MultiPolygon([france_polygon]))],
    )
    return map


@pytest.fixture
def france_zh():
    map = MapFactory(
        name="France map ZH",
        map_type="zone_humide",
        zones=[ZoneFactory(geometry=MultiPolygon([france_polygon]))],
    )
    return map


@pytest.fixture
def bizous_town_center():
    """A map with only Bizous's town center."""

    polygon = Polygon(
        [
            (0.4421436860179369, 43.06930871579473),
            (0.4421088173007432, 43.06925826047046),
            (0.44236765047068033, 43.069162248282396),
            (0.44240386029238143, 43.06922152113057),
            (0.4421436860179369, 43.06930871579473),
        ]
    )
    map = MapFactory(
        name="Bizou town center",
        map_type="",
        zones=[ZoneFactory(geometry=MultiPolygon([polygon]))],
    )
    return map


@pytest.fixture
def loire_atlantique_map():
    map = MapFactory(
        name="Loire Atlantique",
        map_type="",
        zones=[ZoneFactory(geometry=MultiPolygon([loire_atlantique_polygon]))],
    )
    return map


@pytest.fixture
def herault_map():
    map = MapFactory(
        name="Hérault",
        map_type="",
        zones=[ZoneFactory(geometry=MultiPolygon([herault_polygon]))],
    )
    return map


@pytest.fixture
def loire_atlantique_department():
    loire_atlantique = DepartmentFactory(
        department=44, geometry=MultiPolygon([loire_atlantique_polygon])
    )
    return loire_atlantique
