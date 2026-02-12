from datetime import date, timedelta

import pytest
from django.contrib.sites.models import Site
from django.db.backends.postgresql.psycopg_any import DateRange
from django.test import override_settings
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site() -> Site:
    return SiteFactory()


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@pytest.mark.urls("config.urls_haie")
def test_hedge_input_without_config_should_have_default_hedge_properties_form(client):
    """When dept. contact info is not set, eval is unavailable."""

    url = reverse("input_hedges", args=["02", "plantation"])
    res = client.get(url)

    assert res.status_code == 200
    assert 'name="plantation-sur_parcelle_pac"' in res.content.decode()
    assert 'name="plantation-connexion_boisement"' not in res.content.decode()


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@pytest.mark.urls("config.urls_haie")
def test_hedge_input_with_config_should_have_set_hedge_properties_form(client):
    """When dept. contact info is not set, eval is unavailable."""
    DCConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesCalvadosForm",
    )
    url = reverse("input_hedges", args=["44", "plantation"])
    res = client.get(url)

    assert res.status_code == 200
    assert 'name="plantation-sur_parcelle_pac"' in res.content.decode()
    assert 'name="plantation-connexion_boisement"' in res.content.decode()
    assert 'name="removal-connexion_boisement"' not in res.content.decode()

    assert 'name="plantation-essences_non_bocageres"' not in res.content.decode()
    assert 'name="removal-essences_non_bocageres"' in res.content.decode()


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@pytest.mark.urls("config.urls_haie")
def test_hedge_input_conditions_url(client):
    """Test url to get condition."""
    DCConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesCalvadosForm",
    )
    project = PetitionProjectFactory()
    url = reverse("input_hedges", args=["44", "read_only", project.hedge_data.id])
    res = client.get(url)
    assert "Conditions à respecter pour la plantation" in res.content.decode()


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@pytest.mark.urls("config.urls_haie")
def test_hedge_input_uses_config_matching_simulation_date(client):
    """The date query param selects the correct config for hedge form properties."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    one_year_later = today + timedelta(days=365)

    # Old config with custom form properties (e.g. Calvados)
    DCConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        validity_range=DateRange(one_year_ago, today, "[)"),
    )
    # Current config with default form properties
    DCConfigHaieFactory(
        validity_range=DateRange(today, one_year_later, "[)"),
    )

    # Simulation with a past date → should use the old config's form
    past_date = (today - timedelta(days=30)).strftime("%Y%m%d")
    url = reverse("input_hedges", args=["44", "plantation"])
    res = client.get(url, {"department": "44", "date": past_date})
    assert res.status_code == 200
    assert 'name="plantation-connexion_boisement"' in res.content.decode()

    # Simulation with today's date → should use the current config's default form
    today_str = today.strftime("%Y%m%d")
    res = client.get(url, {"department": "44", "date": today_str})
    assert res.status_code == 200
    assert 'name="plantation-connexion_boisement"' not in res.content.decode()
