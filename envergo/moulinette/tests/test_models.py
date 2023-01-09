import pytest

from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.geodata.tests.factories import DepartmentFactory, ZoneFactory
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import PerimeterFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def loisurleau_criterions(france_map):  # noqa

    classes = [
        "envergo.moulinette.regulations.loisurleau.ZoneHumide",
        "envergo.moulinette.regulations.loisurleau.ZoneInondable",
        "envergo.moulinette.regulations.loisurleau.Ruissellement",
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


@pytest.fixture
def bizous_church_data(footprint):
    return {
        "lat": 43.068835,
        "lng": 0.442846,
        "existing_surface": 0,
        "created_surface": footprint,
    }


def no_zones(_coords):
    return []


def create_zones():
    return [ZoneFactory()]


@pytest.mark.parametrize("footprint", [50])
def test_result_without_contact_data(moulinette_data):
    """When dept. contact info is not set, we cannot run the eval."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.is_evaluation_available()


@pytest.mark.parametrize("footprint", [50])
def test_result_with_contact_data(moulinette_data):
    """Dept contact info is not set, we can run the eval."""

    DepartmentFactory(department=61)

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.is_evaluation_available()


@pytest.mark.parametrize("footprint", [50])
def test_moulinette_get_perimeters_distance(
    bizous_church_data, bizous_town_center  # noqa
):
    """Check the `activation_distance` Perimeter field.

    We check that we activate all perimeters that are within
    `activation_distance` of the evaluation coordinates.
    """

    DepartmentFactory(department=61)

    # We create a project that has the shape of Bizous's church…
    moulinette = Moulinette(bizous_church_data, bizous_church_data)
    assert len(moulinette.get_perimeters()) == 3

    # and a `ZoneHumide` perimeter with the shape of Bizous's town center
    perimeter = PerimeterFactory(
        map=bizous_town_center,
        criterion="envergo.moulinette.regulations.loisurleau.ZoneHumide",
    )
    assert len(moulinette.get_perimeters()) == 3

    # There is approx. 45 ~_50m between the church and town center
    perimeter.activation_distance = 30
    perimeter.save()
    assert len(moulinette.get_perimeters()) == 3

    perimeter.activation_distance = 60
    perimeter.save()
    assert len(moulinette.get_perimeters()) == 4
