import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.geodata.tests.factories import ZoneFactory
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import PerimeterFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def loisurleau_criterions(france_map):  # noqa

    classes = [
        "envergo.moulinette.regulations.natura2000.IOTA",
        "envergo.moulinette.regulations.loisurleau.ZoneHumide",
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
    }


def no_zones(_coords):
    return []


def create_zones():
    return [ZoneFactory()]


@pytest.mark.parametrize("footprint", [700])
def test_zh_medium_footprint_inside_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"
    assert moulinette.natura2000.iota.result == "a_verifier"
    assert moulinette.natura2000.result == "iota_a_verifier"
