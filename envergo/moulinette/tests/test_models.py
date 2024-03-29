import pytest

from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.geodata.tests.factories import ZoneFactory
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def moulinette_config(france_map):  # noqa
    regulation = RegulationFactory()
    PerimeterFactory(
        regulation=regulation,
        activation_map=france_map,
    )
    classes = [
        "envergo.moulinette.regulations.loisurleau.ZoneHumide",
        "envergo.moulinette.regulations.loisurleau.ZoneInondable",
        "envergo.moulinette.regulations.loisurleau.Ruissellement",
    ]
    for path in classes:
        CriterionFactory(
            regulation=regulation, activation_map=france_map, evaluator=path
        )


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.4961953,
        "lng": 0.7504093,
        "created_surface": 0,
        "final_surface": footprint,
    }


@pytest.fixture
def bizous_church_data(footprint):
    return {
        "lat": 43.068835,
        "lng": 0.442846,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
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
def test_moulinette_config(moulinette_data):
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.has_config()

    MoulinetteConfigFactory(is_activated=False)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.has_config()


@pytest.mark.parametrize("footprint", [50])
def test_result_with_inactive_contact_data(moulinette_data):
    """Dept contact info is not activated, we cannot run the eval."""

    MoulinetteConfigFactory(is_activated=False)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert not moulinette.is_evaluation_available()


@pytest.mark.parametrize("footprint", [50])
def test_result_with_contact_data(moulinette_data):
    """Dept contact info is set, we can run the eval."""

    MoulinetteConfigFactory(is_activated=True)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.is_evaluation_available()
