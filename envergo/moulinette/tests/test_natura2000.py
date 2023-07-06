import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def n2000_criteria(france_map):  # noqa
    regulation = RegulationFactory(
        title="Natura 2000", slug="natura2000", perimeter=france_map
    )
    criteria = [
        CriterionFactory(
            title="Zone humide 44",
            slug="zone_humide_44",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneHumide44",
            perimeter=france_map,
        ),
        CriterionFactory(
            title="Zone inondable 44",
            slug="zone_inondable_44",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneInondable44",
            perimeter=france_map,
        ),
        CriterionFactory(
            title="IOTA",
            slug="iota",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.IOTA",
            perimeter=france_map,
        ),
    ]
    return criteria


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


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_outside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_inside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "non_soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_within_wetlands(moulinette_data):
    """Project with footprint >= 100m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_close_to_wetlands(moulinette_data):
    """Project with footprint >= 100m² close to a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_inside_potential_wetland(moulinette_data):
    """Project with footprint >= 100m² inside a potential wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_outside_wetlands(moulinette_data):
    """Project with footprint > 100m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide_44.result == "non_concerne"


@pytest.mark.parametrize("footprint", [150])
def test_zi_small_footprint(moulinette_data):
    """Project with footprint < 200m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable_44.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_within_flood_zones(moulinette_data):
    """Project with footprint >= 200m² within a flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable_44.result == "soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_outside_flood_zones(moulinette_data):
    """Project footprint >= 200m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable_44.result == "non_concerne"
