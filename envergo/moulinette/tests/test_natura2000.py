import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.geodata.tests.factories import ZoneFactory
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import PerimeterFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def loisurleau_criterions(france_map):  # noqa

    classes = [
        "envergo.moulinette.regulations.natura2000.ZoneHumide44",
        "envergo.moulinette.regulations.natura2000.ZoneInondable44",
        "envergo.moulinette.regulations.natura2000.Lotissement44",
    ]
    perimeters = [PerimeterFactory(map=france_map, criterion=path) for path in classes]
    return perimeters


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.4961953,
        "lng": 0.7504093,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
    }


def no_zones(_coords):
    return []


def create_zones():
    return [ZoneFactory()]


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_outside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    assert moulinette.natura2000.zone_humide_44.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_inside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    assert moulinette.natura2000.zone_humide_44.result == "non_soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_within_wetlands(moulinette_data):
    """Project with footprint >= 100m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    assert moulinette.natura2000.zone_humide_44.result == "soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_close_to_wetlands(moulinette_data):
    """Project with footprint >= 100m² close to a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    assert moulinette.natura2000.zone_humide_44.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_inside_potential_wetland(moulinette_data):
    """Project with footprint >= 100m² inside a potential wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_0m"] = True
    assert moulinette.natura2000.zone_humide_44.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_outside_wetlands(moulinette_data):
    """Project with footprint > 100m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.natura2000.zone_humide_44.result == "non_concerne"


@pytest.mark.parametrize("footprint", [150])
def test_zi_small_footprint(moulinette_data):
    """Project with footprint < 200m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    assert moulinette.natura2000.zone_inondable_44.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_within_flood_zones(moulinette_data):
    """Project with footprint >= 200m² within a flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    assert moulinette.natura2000.zone_inondable_44.result == "soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_outside_flood_zones(moulinette_data):
    """Project footprint >= 200m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.natura2000.zone_inondable_44.result == "non_concerne"
