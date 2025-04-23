import pytest
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.moulinette.tests.factories import ConfigHaieFactory

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
    assert (
        '<input type="checkbox" name="plantation-sur_parcelle_pac" id="id_plantation-sur_parcelle_pac">'
        in res.content.decode()
    )
    assert (
        '<input type="checkbox" name="plantation-connexion_boisement" id="id_plantation-connexion_boisement">'
        not in res.content.decode()
    )


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@pytest.mark.urls("config.urls_haie")
def test_hedge_input_with_config_should_have_set_hedge_properties_form(client):
    """When dept. contact info is not set, eval is unavailable."""
    ConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesCalvadosForm",
    )
    url = reverse("input_hedges", args=["44", "plantation"])
    res = client.get(url)

    assert res.status_code == 200
    assert (
        '<input type="checkbox" name="plantation-sur_parcelle_pac" id="id_plantation-sur_parcelle_pac">'
        in res.content.decode()
    )
    assert (
        '<input type="checkbox" name="plantation-connexion_boisement" id="id_plantation-connexion_boisement">'
        in res.content.decode()
    )
    assert (
        '<input type="checkbox" name="removal-connexion_boisement" id="id_removal-connexion_boisement">'
        not in res.content.decode()
    )

    assert (
        '<input type="checkbox" name="plantation-essences_non_bocageres" id="id_plantation-essences_non_bocageres">'
        not in res.content.decode()
    )
    assert (
        '<input type="checkbox" name="removal-essences_non_bocageres" id="id_removal-essences_non_bocageres">'
        in res.content.decode()
    )
