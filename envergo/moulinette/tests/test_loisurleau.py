import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def loisurleau_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="loi_sur_leau")
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneHumide",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Zone inondable",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneInondable",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Ruissellement",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.Ruissellement",
            activation_map=france_map,
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
def test_3310_small_footprint_outside_wetlands(moulinette_data):
    """Project with footprint < 700m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_3310_small_footprint_inside_wetlands(moulinette_data):
    """Project with footprint < 700m² are not subject to the 3310."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [700])
def test_3310_medium_footprint_inside_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_wetlands_2(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_close_to_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² close to a wetland."""

    # Make sure the project in close to a wetland
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_potential_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² inside a potential wetland."""

    # Make sure the project is in a potential wetland
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_outside_wetlands(moulinette_data):
    """Project with 700 < footprint < 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_within_wetlands(moulinette_data):
    """Project with footprint >= 1000m² within a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_close_to_wetlands(moulinette_data):
    """Project with footprint >= 1000m² close to a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_inside_potential_wetland(moulinette_data):
    """Project with footprint >= 1000m² inside a potential wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_outside_wetlands(moulinette_data):
    """Project with footprint > 1000m² outside a wetland."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [299])
def test_3220_small_footprint(moulinette_data):
    """Project with footprint < 300m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_within_flood_zones(moulinette_data):
    """Project with 500m² < footprint <= 300m² within a flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_outside_flood_zones(moulinette_data):
    """Project with 500m² < footprint <= 300m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [200])
def test_3220_small_footprint_outside_flood_zones(moulinette_data):
    """Project with small footprint outside a flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_within_flood_zones(moulinette_data):
    """Project with footprint >= 400m² within a flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "soumis"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_outside_flood_zones(moulinette_data):
    """Project with footprint >= 400m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_within_potential_flood_zones(moulinette_data):
    """Project with footprint >= 400m² within a potential flood zone."""

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_within_potential_flood_zones(moulinette_data):
    """Project with footprint >= 400m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"
