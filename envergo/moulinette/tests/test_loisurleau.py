from unittest.mock import patch

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def loisurleau_criteria(france_map):  # noqa
    regulation = RegulationFactory(
        regulation="loi_sur_leau",
        evaluator="envergo.moulinette.regulations.loisurleau.LoiSurLEauRegulation",
    )
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
        CriterionFactory(
            title="Écoulement EP sans BV",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.EcoulementSansBV",
            activation_map=france_map,
            is_optional=True,
        ),
        CriterionFactory(
            title="Écoulement EP avec BV",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.EcoulementAvecBV",
            activation_map=france_map,
            is_optional=True,
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(footprint):
    data = {
        # Mouais coordinates
        "lat": 47.696706,
        "lng": -1.646947,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize("footprint", [50])
def test_3310_small_footprint_outside_wetlands(moulinette_data):
    """Project with footprint < 700m² are not subject to the 3310."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_3310_small_footprint_inside_wetlands(moulinette_data):
    """Project with footprint < 700m² are not subject to the 3310."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [700])
def test_3310_medium_footprint_inside_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_wetlands_2(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_close_to_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² close to a wetland."""

    # Make sure the project in close to a wetland
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_inside_potential_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² inside a potential wetland."""

    # Make sure the project is in a potential wetland
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [800])
def test_3310_medium_footprint_outside_wetlands(moulinette_data):
    """Project with 700 < footprint < 1000m² outside a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_within_wetlands(moulinette_data):
    """Project with footprint >= 1000m² within a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_close_to_wetlands(moulinette_data):
    """Project with footprint >= 1000m² close to a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_inside_potential_wetland(moulinette_data):
    """Project with footprint >= 1000m² inside a potential wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_outside_wetlands(moulinette_data):
    """Project with footprint > 1000m² outside a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [1500])
def test_3310_large_footprint_inside_doubt_department(moulinette_data):
    """Project with footprint > 1000m² inside a whole zh department."""

    ConfigAmenagementFactory(zh_doubt=True)
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["within_potential_wetlands_department"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [299])
def test_3220_small_footprint(moulinette_data):
    """Project with footprint < 300m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_within_flood_zones(moulinette_data):
    """Project with 500m² < footprint <= 300m² within a flood zone."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_outside_flood_zones(moulinette_data):
    """Project with 500m² < footprint <= 300m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [200])
def test_3220_small_footprint_outside_flood_zones(moulinette_data):
    """Project with small footprint outside a flood zone."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_within_flood_zones(moulinette_data):
    """Project with footprint >= 400m² within a flood zone."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "soumis"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_outside_flood_zones(moulinette_data):
    """Project with footprint >= 400m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [400])
def test_3220_large_footprint_within_potential_flood_zones(moulinette_data):
    """Project with footprint >= 400m² within a potential flood zone."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


@pytest.mark.parametrize("footprint", [300])
def test_3220_medium_footprint_within_potential_flood_zones(moulinette_data):
    """Project with footprint >= 400m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


@pytest.mark.parametrize("footprint", [9000])
def test_2150_not_so_big(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "action_requise"


@pytest.mark.parametrize("footprint", [10000])
def test_2150_big(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "soumis_ou_pac"


@pytest.mark.parametrize("footprint", [8000])
def test_2150_medium(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "action_requise"


@pytest.mark.parametrize("footprint", [7000])
def test_2150_small(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_2150_with_pv_sol_big(moulinette_data):
    moulinette_data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert (
        moulinette.loi_sur_leau.ecoulement_sans_bv.result_code
        == "action_requise_pv_sol"
    )


@pytest.mark.parametrize("footprint", [8000])
def test_2150_with_pv_sol_small(moulinette_data):
    moulinette_data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "non_soumis_pv_sol"


@pytest.mark.parametrize("footprint", [10000])
def test_2150_avec_bv_big(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "soumis"


@pytest.mark.parametrize("footprint", [9000])
def test_2150_avec_bv_medium(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "action_requise"


@pytest.mark.parametrize("footprint", [7000])
def test_2150_avec_bv_small(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis"


@patch("envergo.moulinette.regulations.loisurleau.get_catchment_area")
@pytest.mark.parametrize("footprint", [1400])
def test_2150_avec_bv_small_but_big_bv(mock_get_catchment_area, moulinette_data):
    mock_get_catchment_area.return_value = 12000
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis"


@patch("envergo.moulinette.regulations.loisurleau.get_catchment_area")
@pytest.mark.parametrize("footprint", [1600])
def test_2150_avec_bv_medium_but_big_bv(mock_get_catchment_area, moulinette_data):
    mock_get_catchment_area.return_value = 12000
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "action_requise"


@pytest.mark.parametrize("footprint", [10000])
def test_2150_avec_bv_with_pv_sol_big(moulinette_data):
    moulinette_data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert (
        moulinette.loi_sur_leau.ecoulement_avec_bv.result_code
        == "action_requise_pv_sol"
    )


@pytest.mark.parametrize("footprint", [8000])
def test_2150_avec_bv_with_pv_sol_small(moulinette_data):
    moulinette_data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis_pv_sol"


@pytest.mark.parametrize("footprint", [700])
def test_moulinette_returns_actions_to_take(moulinette_data):
    ConfigAmenagementFactory()
    moulinette = MoulinetteAmenagement(moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"
    assert moulinette.loi_sur_leau.actions_to_take == {"to_add": {"mention_arrete_lse"}}
    assert moulinette.loi_sur_leau.zone_humide.actions_to_take == {
        "to_add": {"etude_zh"}
    }
    actions_to_take_flatten = {
        target: [action.slug for action in actions_list]
        for target, actions_list in moulinette.actions_to_take.items()
    }
    assert actions_to_take_flatten == {
        "instructor": ["mention_arrete_lse"],
        "petitioner": ["etude_zh"],
    }
