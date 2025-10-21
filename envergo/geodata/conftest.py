import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.geodata.tests.factories import (
    DepartmentFactory,
    MapFactory,
    aisne_polygon,
    calvados_polygon,
    france_polygon,
    herault_polygon,
    loire_atlantique_polygon,
)


@pytest.fixture
def france_map():
    """Fixture for a map containing mainland France territory."""

    map = MapFactory(
        name="France map",
        map_type="",
        zones__geometry=MultiPolygon([france_polygon]),
    )
    return map


@pytest.fixture
def france_zh():
    map = MapFactory(
        name="France map ZH",
        map_type="zone_humide",
        zones__geometry=MultiPolygon([france_polygon]),
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
        zones__geometry=MultiPolygon([polygon]),
    )
    return map


@pytest.fixture
def loire_atlantique_map():
    map = MapFactory(
        name="Loire Atlantique",
        map_type="",
        zones__geometry=MultiPolygon([loire_atlantique_polygon]),
    )
    return map


@pytest.fixture
def herault_map():
    map = MapFactory(
        name="Hérault",
        map_type="",
        zones__geometry=MultiPolygon([herault_polygon]),
    )
    return map


@pytest.fixture
def aisne_map():
    map = MapFactory(
        name="Aisne",
        map_type="",
        zones__geometry=MultiPolygon([aisne_polygon]),
    )
    return map


@pytest.fixture
def calvados_map():
    map = MapFactory(
        name="Calvados",
        map_type="",
        zones__geometry=MultiPolygon([calvados_polygon]),
    )
    return map


@pytest.fixture
def loire_atlantique_department():
    loire_atlantique = DepartmentFactory(
        department=44, geometry=MultiPolygon([loire_atlantique_polygon])
    )
    return loire_atlantique
