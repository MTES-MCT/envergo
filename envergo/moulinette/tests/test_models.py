import pytest

from envergo.geodata.conftest import france_map  # noqa
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


def no_zones(_coords):
    return []


def create_zones(_coords):
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
def test_3310_small_footprint_outside_wetlands(moulinette_data, monkeypatch):
    """Project with footprint < 700m² are not subject to the 3310."""

    # Make sure the project in in a wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_3310_small_footprint_inside_wetlands(moulinette_data, monkeypatch):
    """Project with footprint < 700m² are not subject to the 3310."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [700])
def test_3310_medium_footprint_inside_wetlands(moulinette_data, monkeypatch):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_wetlands_2(moulinette_data, monkeypatch):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_close_to_wetlands(moulinette_data, monkeypatch):
    """Project with 700 <= footprint <= 1000m² close to a wetland."""

    # Make sure the project in close to a wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_100m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_potential_wetlands(moulinette_data, monkeypatch):
    """Project with 700 <= footprint <= 1000m² inside a potential wetland."""

    # Make sure the project is in a potential wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_100m", no_zones
    )
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_potential_wetlands", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_outside_wetlands(moulinette_data):
    """Project with 700 < footprint < 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_within_wetlands(moulinette_data, monkeypatch):
    """Project with footprint >= 1000m² within a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_25m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_close_to_wetlands(moulinette_data, monkeypatch):
    """Project with footprint >= 1000m² close to a wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_100m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_inside_potential_wetland(moulinette_data, monkeypatch):
    """Project with footprint >= 1000m² inside a potential wetland."""

    # Make sure the project in in a wetland
    monkeypatch.setattr("envergo.moulinette.models.fetch_wetlands_around_25m", no_zones)
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_wetlands_around_100m", no_zones
    )
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_potential_wetlands", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_outside_wetlands(moulinette_data, monkeypatch):
    """Project with footprint > 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [299])
def test_3220_small_footprint(moulinette_data, monkeypatch):
    """Project with footprint < 300m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_within_flood_zones(moulinette_data, monkeypatch):
    """Project with 500m² < footprint <= 300m² within a flood zone."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_outside_flood_zones(moulinette_data, monkeypatch):
    """Project with 500m² < footprint <= 300m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_within_flood_zones(moulinette_data, monkeypatch):
    """Project with footprint >= 400m² within a flood zone."""

    # Make sure the project in in a flood zone
    monkeypatch.setattr(
        "envergo.moulinette.models.fetch_flood_zones_around_12m", create_zones
    )

    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_inondable.result == "soumis"


@pytest.mark.parametrize("footprint", [300])
def test_3220_large_footprint_outside_flood_zones(moulinette_data):
    """Project with footprint >= 400m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"
