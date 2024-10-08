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
    ConfigAmenagementFactory(
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
    )
    lse = RegulationFactory(regulation="loi_sur_leau")
    n2000 = RegulationFactory(regulation="natura2000")
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=lse,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneHumide",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="IOTA",
            regulation=n2000,
            evaluator="envergo.moulinette.regulations.natura2000.IOTA",
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
    }


@pytest.mark.parametrize("footprint", [700])
def test_zh_medium_footprint_inside_wetlands(moulinette_data):
    """Project with 700 <= footprint <= 1000m² within a wetland."""

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"
    assert moulinette.natura2000.iota.result == "iota_a_verifier"
    assert moulinette.natura2000.result == "iota_a_verifier"
