import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Criterion, MoulinetteAmenagement
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


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


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.4961953,
        "lng": 0.7504093,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
        "autorisation_urba": "none",
    }


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_outside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [50])
def test_zh_small_footprint_inside_wetlands(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_small_footprint_inside_wetlands_with_custom_threshold(moulinette_data):
    """Project with footprint < 100m² are not subject to the 3310."""
    Criterion.objects.filter(title="Zone humide 44").update(
        evaluator_settings={"threshold": 200}
    )
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_within_wetlands(moulinette_data):
    """Project with footprint >= 100m² within a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "soumis"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_close_to_wetlands(moulinette_data):
    """Project with footprint >= 100m² close to a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_inside_potential_wetland(moulinette_data):
    """Project with footprint >= 100m² inside a potential wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = False
    moulinette.catalog["wetlands_within_100m"] = False
    moulinette.catalog["potential_wetlands_within_10m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "action_requise"


@pytest.mark.parametrize("footprint", [150])
def test_zh_large_footprint_outside_wetlands(moulinette_data):
    """Project with footprint > 100m² outside a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.natura2000.zone_humide.result == "non_concerne"


@pytest.mark.parametrize("footprint", [150])
def test_zi_small_footprint(moulinette_data):
    """Project with footprint < 200m² are not subject to the 3320."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "non_soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_within_flood_zones(moulinette_data):
    """Project with footprint >= 200m² within a flood zone."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["flood_zones_within_12m"] = True
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "soumis"


@pytest.mark.parametrize("footprint", [300])
def test_zi_medium_footprint_outside_flood_zones(moulinette_data):
    """Project footprint >= 200m² outside a flood zone."""

    # Make sure the project in in a flood zone
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.natura2000.zone_inondable.result == "non_concerne"


@pytest.mark.parametrize("footprint", [300])
def test_autorisation_urba_value(moulinette_data):
    """Check the custom "autorisation_urba" property.

    We need a custom property to check if the project requires an
    "autorisation d'urbanisme".

    It will always be the case unless the user explicitly states otherwise.
    """
    moulinette_data["autorisation_urba"] = "pa"
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    assert moulinette.natura2000.autorisation_urba.result == "soumis"
    assert moulinette.natura2000.autorisation_urba_needed() is True

    moulinette_data["autorisation_urba"] = "other"
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    assert moulinette.natura2000.autorisation_urba.result == "a_verifier"
    assert moulinette.natura2000.autorisation_urba_needed() is True

    moulinette_data["autorisation_urba"] = "none"
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    assert moulinette.natura2000.autorisation_urba.result == "non_soumis"
    assert moulinette.natura2000.autorisation_urba_needed() is False

    del moulinette_data["autorisation_urba"]
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    assert moulinette.natura2000.autorisation_urba.result == "non_disponible"
    assert moulinette.natura2000.autorisation_urba_needed() is True
