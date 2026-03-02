from unittest.mock import patch

import pytest

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ActionToTakeFactory,
    ConfigAmenagementFactory,
)
from envergo.moulinette.tests.utils import make_amenagement_data, setup_loi_sur_leau


@pytest.fixture(autouse=True)
def loisurleau_criteria(france_map):  # noqa
    return setup_loi_sur_leau(france_map)


# ---------------------------------------------------------------------------
# Rubrique 3310 — Zone humide
# ---------------------------------------------------------------------------


def test_3310_small_footprint_outside_wetlands():
    """Project with footprint < 700m² are not subject to the 3310."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=50, final_surface=50)
    )
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


def test_3310_small_footprint_inside_wetlands():
    """Project with footprint < 700m² are not subject to the 3310."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=50, final_surface=50)
    )
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


def test_3310_medium_footprint_inside_wetlands():
    """Project with 700 <= footprint <= 1000m² within a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=700, final_surface=700)
    )
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


def test_3310_medium_footprint_inside_wetlands_2():
    """Project with 700 <= footprint <= 1000m² within a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=800, final_surface=800)
    )
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


def test_3310_medium_footprint_close_to_wetlands():
    """Project with 700 <= footprint <= 1000m² close to a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=800, final_surface=800)
    )
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


def test_3310_medium_footprint_inside_potential_wetlands():
    """Project with 700 <= footprint <= 1000m² inside a potential wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=800, final_surface=800)
    )
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"


def test_3310_medium_footprint_outside_wetlands():
    """Project with 700 < footprint < 1000m² outside a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=800, final_surface=800)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


def test_3310_large_footprint_within_wetlands():
    """Project with footprint >= 1000m² within a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1500, final_surface=1500)
    )
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"


def test_3310_large_footprint_close_to_wetlands():
    """Project with footprint >= 1000m² close to a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1500, final_surface=1500)
    )
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


def test_3310_large_footprint_inside_potential_wetland():
    """Project with footprint >= 1000m² inside a potential wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1500, final_surface=1500)
    )
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


def test_3310_large_footprint_outside_wetlands():
    """Project with footprint > 1000m² outside a wetland."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1500, final_surface=1500)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_concerne"


def test_3310_large_footprint_inside_doubt_department():
    """Project with footprint > 1000m² inside a whole zh department."""
    ConfigAmenagementFactory(zh_doubt=True)
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1500, final_surface=1500)
    )
    moulinette.catalog["within_potential_wetlands_department"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"


# ---------------------------------------------------------------------------
# Rubrique 3220 — Zone inondable
# ---------------------------------------------------------------------------


def test_3220_small_footprint():
    """Project with footprint < 300m² are not subject to the 3320."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=299, final_surface=299)
    )
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


def test_3220_medium_footprint_within_flood_zones():
    """Project with 500m² < footprint <= 300m² within a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=300, final_surface=300)
    )
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


def test_3220_medium_footprint_outside_flood_zones():
    """Project with 500m² < footprint <= 300m² outside a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=300, final_surface=300)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


def test_3220_small_footprint_outside_flood_zones():
    """Project with small footprint outside a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=200, final_surface=200)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


def test_3220_large_footprint_within_flood_zones():
    """Project with footprint >= 400m² within a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=400, final_surface=400)
    )
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "soumis"


def test_3220_large_footprint_outside_flood_zones():
    """Project with footprint >= 400m² outside a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=400, final_surface=400)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_concerne"


def test_3220_large_footprint_within_potential_flood_zones():
    """Project with footprint >= 400m² within a potential flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=400, final_surface=400)
    )
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "action_requise"


def test_3220_medium_footprint_within_potential_flood_zones():
    """Project with footprint >= 400m² outside a flood zone."""
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=300, final_surface=300)
    )
    moulinette.catalog["potential_flood_zones_within_0m"] = True
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.zone_inondable.result == "non_soumis"


# ---------------------------------------------------------------------------
# Rubrique 2150 — Écoulement EP (sans bassin versant)
# ---------------------------------------------------------------------------


def test_2150_not_so_big():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=9000, final_surface=9000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "action_requise"


def test_2150_big():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=10000, final_surface=10000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "soumis_ou_pac"


def test_2150_medium():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=8000, final_surface=8000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "action_requise"


def test_2150_small():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=7000, final_surface=7000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "non_soumis"


def test_2150_with_pv_sol_big():
    data = make_amenagement_data(created_surface=10000, final_surface=10000)
    data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(data)
    moulinette.evaluate()
    assert (
        moulinette.loi_sur_leau.ecoulement_sans_bv.result_code
        == "action_requise_pv_sol"
    )


def test_2150_with_pv_sol_small():
    data = make_amenagement_data(created_surface=8000, final_surface=8000)
    data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_sans_bv.result_code == "non_soumis_pv_sol"


# ---------------------------------------------------------------------------
# Rubrique 2150 — Écoulement EP (avec bassin versant)
# ---------------------------------------------------------------------------


def test_2150_avec_bv_big():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=10000, final_surface=10000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "soumis"


def test_2150_avec_bv_medium():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=9000, final_surface=9000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "action_requise"


def test_2150_avec_bv_small():
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=7000, final_surface=7000)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis"


@patch("envergo.moulinette.regulations.loisurleau.get_catchment_area")
def test_2150_avec_bv_small_but_big_bv(mock_get_catchment_area):
    mock_get_catchment_area.return_value = 12000
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1400, final_surface=1400)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis"


@patch("envergo.moulinette.regulations.loisurleau.get_catchment_area")
def test_2150_avec_bv_medium_but_big_bv(mock_get_catchment_area):
    mock_get_catchment_area.return_value = 12000
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=1600, final_surface=1600)
    )
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "action_requise"


def test_2150_avec_bv_with_pv_sol_big():
    data = make_amenagement_data(created_surface=10000, final_surface=10000)
    data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(data)
    moulinette.evaluate()
    assert (
        moulinette.loi_sur_leau.ecoulement_avec_bv.result_code
        == "action_requise_pv_sol"
    )


def test_2150_avec_bv_with_pv_sol_small():
    data = make_amenagement_data(created_surface=8000, final_surface=8000)
    data["data"]["evalenv_rubrique_30-localisation"] = "sol"
    moulinette = MoulinetteAmenagement(data)
    moulinette.evaluate()
    assert moulinette.loi_sur_leau.ecoulement_avec_bv.result_code == "non_soumis_pv_sol"


# ---------------------------------------------------------------------------
# Actions to take
# ---------------------------------------------------------------------------


def test_moulinette_returns_actions_to_take():
    ConfigAmenagementFactory()
    ActionToTakeFactory(slug="mention_arrete_lse")
    ActionToTakeFactory(slug="etude_zh", target="petitioner")
    moulinette = MoulinetteAmenagement(
        make_amenagement_data(created_surface=700, final_surface=700)
    )
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
