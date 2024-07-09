from unittest.mock import Mock, patch

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory, ZoneFactory

# This is a rough pentagon that I manually drew on geoportail and that contains
# France's mainland.
france_pentagon = Polygon(
    [
        (2.239523057461999, 51.37848260569899),
        (-5.437949095065911, 48.830042871275225),
        (-2.020973593289057, 42.22052255703733),
        (7.672371135600932, 42.3263119734425),
        (9.759728555096416, 49.41947007260785),
        (2.239523057461999, 51.37848260569899),
    ]
)


@pytest.fixture
def france_map():
    """Fixture for a map containing mainland France territory."""

    map = MapFactory(name="France map", map_type="")
    ZoneFactory(map=map, geometry=MultiPolygon([france_pentagon]))
    return map


@pytest.fixture
def france_zh():
    map = MapFactory(name="France map", map_type="zone_humide")
    ZoneFactory(map=map, geometry=MultiPolygon([france_pentagon]))
    return map


@pytest.fixture
def bizous_town_center():
    """A map with only Bizous's town center."""

    map = MapFactory(name="Bizou town center", map_type="")
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


@pytest.fixture
def loire_atlantique_department():
    # A very rough polygon of Loire-Atlantique department.
    polygon = Polygon(
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
    loire_atlantique = DepartmentFactory(
        department=44, geometry=MultiPolygon([polygon])
    )
    return loire_atlantique


@pytest.fixture(autouse=True)
def mock_geo_api_data():
    with patch(
        "envergo.geodata.utils.get_data_from_coords", new=Mock()
    ) as mock_geo_data:
        mock_geo_data.return_value = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-1.3866392402397603, 47.14711855636099],
                },
                "properties": {
                    "id": "44070000AR0238",
                    "departmentcode": "44",
                    "municipalitycode": "070",
                    "oldmunicipalitycode": "000",
                    "districtcode": "000",
                    "section": "AR",
                    "sheet": "01",
                    "number": "0238",
                    "city": "La Haie-Fouassière",
                    "distance": 11,
                    "score": 0.9989,
                    "_type": "parcel",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-1.386865, 47.146822]},
                "properties": {
                    "type": "street",
                    "name": "Rue du Breil",
                    "postcode": "44690",
                    "citycode": "44070",
                    "city": "La Haie-Fouassière",
                    "oldcitycode": None,
                    "oldcity": None,
                    "context": "44, Loire-Atlantique, Pays de la Loire",
                    "importance": 0.49222,
                    "id": "44070_0553",
                    "x": 367734.49,
                    "y": 6681070.77,
                    "label": "Rue du Breil 44690 La Haie-Fouassière",
                    "distance": 27,
                    "score": 0.9973,
                    "_type": "address",
                },
            },
        ]
        yield mock_geo_data
