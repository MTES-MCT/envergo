from unittest.mock import patch

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ActionToTakeFactory,
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import (
    flatten_actions_to_take,
    make_amenagement_data,
    setup_loi_sur_leau,
)


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
    assert moulinette.loi_sur_leau.actions_to_take == {
        "to_add": {"mention_arrete_lse"},
        "to_subtract": {"non_depot_lse"},
    }
    assert moulinette.loi_sur_leau.zone_humide.actions_to_take == {
        "to_add": {"etude_zh"}
    }
    actions_to_take_flatten = flatten_actions_to_take(moulinette)
    assert actions_to_take_flatten == {
        "instructor": ["mention_arrete_lse"],
        "petitioner": ["etude_zh"],
    }


# ---------------------------------------------------------------------------
# LSE tests depending on ICPE
# ---------------------------------------------------------------------------

LSE_BASE_PARAMS = (
    "created_surface={surface}&final_surface={surface}&lng=-1.54394&lat=47.21381"
)


@pytest.fixture
def lse_view_setup(france_zh):
    """Set up config for LSE view-level tests (no ICPE criterion)."""
    ConfigAmenagementFactory(is_activated=True)


@pytest.fixture
def lse_icpe_setup(france_map, france_zh):
    """Set up LSE + ICPE criteria for view-level tests."""
    ConfigAmenagementFactory(is_activated=True)
    eval_env_regulation = RegulationFactory(regulation="eval_env")
    CriterionFactory(
        title="ICPE",
        regulation=eval_env_regulation,
        evaluator="envergo.moulinette.regulations.evalenv.ICPE",
        activation_map=france_map,
        is_optional=True,
    )


@pytest.fixture
def lse_icpe_actions():
    """Set up LSE + ICPE actions for actions level tests."""
    ActionToTakeFactory(slug="non_depot_lse", target="petitioner")
    ActionToTakeFactory(slug="mention_arrete_lse")
    ActionToTakeFactory(slug="etude_zh", target="petitioner")


@pytest.mark.usefixtures("lse_icpe_setup", "lse_icpe_actions")
class TestLSEActionsWithICPE:
    """When ICPE result is not non_soumis, tests actions to take according to LSE."""

    def test_lse_action_requise_icpe_moulinette_not_returns_non_depot_lse(self):
        """When LSE result is action_requise then non_depot_lse action is subtracted
        and etude_zh is in actions_to_take."""
        moulinette = MoulinetteAmenagement(
            make_amenagement_data(
                created_surface=700,
                final_surface=700,
                icpe_projet="creation",
                icpe_regime="enregistrement",
            )
        )
        moulinette.catalog["wetlands_within_25m"] = True
        moulinette.evaluate()
        assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"
        assert moulinette.loi_sur_leau.actions_to_take == {
            "to_add": {"mention_arrete_lse"},
            "to_subtract": {"non_depot_lse"},
        }
        assert moulinette.loi_sur_leau.zone_humide.actions_to_take == {
            "to_add": {"etude_zh"}
        }
        actions_to_take_flatten = flatten_actions_to_take(moulinette)
        assert actions_to_take_flatten == {
            "instructor": ["mention_arrete_lse"],
            "petitioner": ["etude_zh"],
        }

    def test_lse_non_soumis_icpe_moulinette_not_returns_non_depot_lse(self):
        """When LSE result is action_requise then non_depot_lse action is subtracted
        and etude_zh is in actions_to_take."""
        moulinette = MoulinetteAmenagement(
            make_amenagement_data(
                created_surface=500,
                final_surface=500,
                icpe_projet="creation",
                icpe_regime="enregistrement",
            )
        )
        moulinette.catalog["wetlands_within_25m"] = True
        moulinette.evaluate()
        assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"
        assert moulinette.loi_sur_leau.actions_to_take == {
            "to_subtract": {"non_depot_lse"}
        }
        assert moulinette.loi_sur_leau.zone_humide.actions_to_take == {}
        actions_to_take_flatten = flatten_actions_to_take(moulinette)
        assert actions_to_take_flatten == {}


# ---------------------------------------------------------------------------
# LSE template selection depending on ICPE
# ---------------------------------------------------------------------------


def _get_lse_url(surface, icpe_projet=None, icpe_regime=None):
    params = LSE_BASE_PARAMS.format(surface=surface)
    if icpe_projet and icpe_regime:
        params += (
            f"&evalenv_icpe-activate=on"
            f"&evalenv_icpe-icpe_projet={icpe_projet}"
            f"&evalenv_icpe-icpe_regime={icpe_regime}"
        )
    return f"{reverse('moulinette_result')}?{params}"


@pytest.mark.usefixtures("lse_view_setup")
class TestLSETemplateWithoutICPE:
    """When ICPE criterion does not exist, LSE uses the sans_icpe templates."""

    def test_soumis_sans_icpe(self, client):
        res = client.get(_get_lse_url(surface=1500))
        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/loi_sur_leau/result_soumis_sans_icpe.html")

    def test_action_requise_sans_icpe(self, client):
        res = client.get(_get_lse_url(surface=800))
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_action_requise_sans_icpe.html"
        )


@pytest.mark.usefixtures("lse_icpe_setup")
class TestLSETemplateWithICPENonSoumis:
    """When ICPE result is non_soumis, LSE uses the sans_icpe templates."""

    def test_soumis_with_icpe_non_soumis(self, client):
        res = client.get(
            _get_lse_url(surface=1500, icpe_projet="aucun", icpe_regime="aucun")
        )
        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/loi_sur_leau/result_soumis_sans_icpe.html")

    def test_action_requise_with_icpe_non_soumis(self, client):
        res = client.get(
            _get_lse_url(surface=800, icpe_projet="aucun", icpe_regime="aucun")
        )
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_action_requise_sans_icpe.html"
        )


@pytest.mark.usefixtures("lse_icpe_setup")
class TestLSETemplateWithICPEActive:
    """When ICPE result is not non_soumis, LSE uses the avec_icpe templates."""

    def test_soumis_with_icpe_cas_par_cas(self, client):
        res = client.get(
            _get_lse_url(
                surface=1500, icpe_projet="creation", icpe_regime="enregistrement"
            )
        )
        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/loi_sur_leau/result_soumis_avec_icpe.html")

    def test_action_requise_with_icpe_cas_par_cas(self, client):
        res = client.get(
            _get_lse_url(
                surface=800, icpe_projet="creation", icpe_regime="enregistrement"
            )
        )
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_action_requise_avec_icpe.html"
        )

    def test_soumis_with_icpe_declaration_creation_uses_avec_icpe(self, client):
        """ICPE declaration/creation has result_code non_soumis_declaration_creation.

        Even though the ICPE result maps to non_soumis, the project still
        involves an ICPE, so LSE must use the avec_icpe template.
        """
        res = client.get(
            _get_lse_url(
                surface=1500, icpe_projet="creation", icpe_regime="declaration"
            )
        )
        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/loi_sur_leau/result_soumis_avec_icpe.html")

    def test_soumis_ou_pac_with_icpe_declaration_creation(self, client):
        """ICPE declaration/creation → result_code non_soumis_declaration_creation.

        The LSE regulation result is soumis_ou_pac (driven by EcoulementSansBV
        at surface >= 10000). The project involves an ICPE, so the avec_icpe
        template must be used.
        """
        res = client.get(
            _get_lse_url(
                surface=10000, icpe_projet="creation", icpe_regime="declaration"
            )
        )
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_soumis_ou_pac_avec_icpe.html"
        )

    def test_action_requise_with_icpe_declaration_creation(self, client):
        """ICPE declaration/creation → has_icpe is True for action_requise too."""
        res = client.get(
            _get_lse_url(surface=800, icpe_projet="creation", icpe_regime="declaration")
        )
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_action_requise_avec_icpe.html"
        )

    def test_soumis_with_icpe_declaration_modif(self, client):
        """ICPE declaration/modif_avec_pac → result_code non_soumis_declaration_modif.

        Same behavior as non_soumis_declaration_creation: the project involves
        an ICPE, so has_icpe must be True.
        """
        res = client.get(
            _get_lse_url(
                surface=1500, icpe_projet="modif_avec_pac", icpe_regime="declaration"
            )
        )
        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/loi_sur_leau/result_soumis_avec_icpe.html")

    def test_action_requise_with_icpe_a_verifier(self, client):
        res = client.get(
            _get_lse_url(surface=800, icpe_projet="creation", icpe_regime="inconnu")
        )
        assert res.status_code == 200
        assertTemplateUsed(
            res, "moulinette/loi_sur_leau/result_action_requise_avec_icpe.html"
        )
