import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.geodata.tests.factories import DepartmentFactory, ZoneFactory
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import PerimeterFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def evalenv_criterions(france_map):  # noqa

    classes = [
        "envergo.moulinette.regulations.evalenv.Emprise",
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


@pytest.mark.parametrize("footprint", [9500])
def test_evalenv_small_footprint(moulinette_data):
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [10500])
def test_evalenv_medium(moulinette_data):
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data['emprise'] = 42
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [40500])
def test_evalenv_wide_footprint(moulinette_data):
    moulinette_data['emprise'] = 42
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data['zone_u'] = 'oui'
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.has_missing_data()
