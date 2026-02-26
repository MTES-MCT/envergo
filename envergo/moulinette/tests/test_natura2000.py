import pytest

from envergo.moulinette.models import Criterion, MoulinetteAmenagement
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory
from envergo.moulinette.tests.utils import COORDS_BIZOU, make_amenagement_data


def _bizou_data(created_surface, **extra):
    """Shortcut for Bizou-located amenagement data with N2000 defaults."""
    defaults = {"autorisation_urba": "none"}
    defaults.update(extra)
    return make_amenagement_data(
        lat=COORDS_BIZOU[0],
        lng=COORDS_BIZOU[1],
        created_surface=created_surface,
        final_surface=created_surface,
        **defaults,
    )


@pytest.fixture(autouse=True)
def n2000_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="natura2000")
    criteria = [
        CriterionFactory(
            title="Zone humide 44",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneHumide",
            activation_map=france_map,
            evaluator_settings={"threshold": 100},
        ),
        CriterionFactory(
            title="Zone inondable 44",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneInondable",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="IOTA",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.IOTA",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Autorisation urbanisme",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.AutorisationUrbanisme",
            activation_map=france_map,
            evaluator_settings={
                "result_code_matrix": {
                    "pa": "soumis",
                    "pc": "soumis",
                    "amenagement_dp": "soumis",
                    "construction_dp": "soumis",
                    "none": "non_soumis",
                    "other": "a_verifier",
                }
            },
        ),
    ]
    return criteria


# ---------------------------------------------------------------------------
# Zone humide
# ---------------------------------------------------------------------------


def test_zh_small_footprint_outside_wetlands():
    """Project with footprint < 100m² are not subject to the 3310."""
    moulinette = MoulinetteAmenagement(_bizou_data(50))
    assert moulinette.is_valid(), moulinette.form_errors()
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_concerne"


def test_zh_small_footprint_inside_wetlands():
    """Project with footprint < 100m² are not subject to the 3310."""
    moulinette = MoulinetteAmenagement(_bizou_data(50))
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_soumis"


def test_zh_small_footprint_inside_wetlands_with_custom_threshold():
    """Project with footprint < 100m² are not subject to the 3310."""
    Criterion.objects.filter(title="Zone humide 44").update(
        evaluator_settings={"threshold": 200}
    )
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_soumis"


def test_zh_large_footprint_within_wetlands():
    """Project with footprint >= 100m² within a wetland."""
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "soumis"


def test_zh_large_footprint_close_to_wetlands():
    """Project with footprint >= 100m² close to a wetland."""
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "action_requise"


def test_zh_large_footprint_inside_potential_wetland():
    """Project with footprint >= 100m² inside a potential wetland."""
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "action_requise"


def test_zh_large_footprint_outside_wetlands():
    """Project with footprint > 100m² outside a wetland."""
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_concerne"


# ---------------------------------------------------------------------------
# Zone inondable
# ---------------------------------------------------------------------------


def test_zi_small_footprint():
    """Project with footprint < 200m² are not subject to the 3320."""
    moulinette = MoulinetteAmenagement(_bizou_data(150))
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "non_soumis"


def test_zi_medium_footprint_within_flood_zones():
    """Project with footprint >= 200m² within a flood zone."""
    moulinette = MoulinetteAmenagement(_bizou_data(300))
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "soumis"


def test_zi_medium_footprint_outside_flood_zones():
    """Project footprint >= 200m² outside a flood zone."""
    moulinette = MoulinetteAmenagement(_bizou_data(300))
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "non_concerne"


# ---------------------------------------------------------------------------
# Autorisation d'urbanisme
# ---------------------------------------------------------------------------


def test_autorisation_urba_value():
    """Check the custom "autorisation_urba" property.

    We need a custom property to check if the project requires an
    "autorisation d'urbanisme".

    It will always be the case unless the user explicitly states otherwise.
    """
    moulinette = MoulinetteAmenagement(_bizou_data(300, autorisation_urba="pa"))
    assert moulinette.natura2000.autorisation_urba.result == "soumis"
    assert moulinette.natura2000.autorisation_urba_needed() is True

    moulinette = MoulinetteAmenagement(_bizou_data(300, autorisation_urba="other"))
    assert moulinette.natura2000.autorisation_urba.result == "a_verifier"
    assert moulinette.natura2000.autorisation_urba_needed() is True

    moulinette = MoulinetteAmenagement(_bizou_data(300, autorisation_urba="none"))
    assert moulinette.natura2000.autorisation_urba.result == "non_soumis"
    assert moulinette.natura2000.autorisation_urba_needed() is False

    # When autorisation_urba is missing from data
    data = _bizou_data(300)
    del data["data"]["autorisation_urba"]
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.natura2000.autorisation_urba.result == "non_disponible"
    assert moulinette.natura2000.autorisation_urba_needed() is True
