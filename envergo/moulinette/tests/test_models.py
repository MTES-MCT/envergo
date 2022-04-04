import pytest

from envergo.geodata.tests.factories import ZoneFactory
from envergo.moulinette.models import Moulinette

pytestmark = pytest.mark.django_db


@pytest.fixture
def moulinette_data(footprint):
    return {
        "lat": 48.4961953,
        "lng": 0.7504093,
        "existing_surface": 0,
        "created_surface": footprint,
    }


def no_zones(_coords):
    return []


def create_zones(_coords):
    return [ZoneFactory()]


@pytest.mark.parametrize("footprint", [50])
def test_3310_small_footprint(moulinette_data, monkeypatch):
    """Project with footprint < 700m² are not subject to the 3310."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_wetlands(moulinette_data, monkeypatch):
    """Project with 750 < footprint < 1000m² within a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint(moulinette_data, monkeypatch):
    """Project with 750 < footprint < 1000m² close to a wetland."""

    # Make sure the project in close to a wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_100m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_outside_wetlands(moulinette_data, monkeypatch):
    """Project with 750 < footprint < 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "non_soumis"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_within_wetlands(moulinette_data, monkeypatch):
    """Project with footprint > 1000m² within a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "soumis"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_outside_wetlands(moulinette_data, monkeypatch):
    """Project with footprint > 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3310 == "action_requise"


@pytest.mark.parametrize("footprint", [50])
def test_3220_small_footprint(moulinette_data, monkeypatch):
    """Project with footprint < 350m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3220 == "non_soumis"


@pytest.mark.parametrize("footprint", [400])
def test_3220_medium_footprint_within_flood_zones(moulinette_data, monkeypatch):
    """Project with 500m² < footprint < 350m² within a flood zone."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3220 == "action_requise"


@pytest.mark.parametrize("footprint", [400])
def test_3220_medium_footprint_outside_flood_zones(moulinette_data, monkeypatch):
    """Project with 500m² < footprint < 350m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3220 == "non_soumis"


@pytest.mark.parametrize("footprint", [650])
def test_3220_large_footprint_within_flood_zones(moulinette_data, monkeypatch):
    """Project with footprint > 500m² within a flood zone."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3220 == "soumis"


@pytest.mark.parametrize("footprint", [650])
def test_3220_large_footprint_outside_flood_zones(moulinette_data, monkeypatch):
    """Project with footprint > 500m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data)
    moulinette.run()
    assert moulinette.eval_result_3220 == "non_soumis"
