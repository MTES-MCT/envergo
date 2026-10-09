import json
from datetime import date, timedelta

import pytest
from django.contrib.sites.models import Site
from django.db.backends.postgresql.psycopg_any import DateRange
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.hedges.models import HedgeData
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = [pytest.mark.django_db, pytest.mark.haie]


@pytest.fixture(autouse=True)
def site() -> Site:
    return SiteFactory()


def test_hedge_input_without_config_should_have_default_hedge_properties_form(client):
    """When dept. contact info is not set, eval is unavailable."""

    url = reverse("input_hedges", args=["02", "plantation"])
    res = client.get(url)

    assert res.status_code == 200
    assert 'name="plantation-sur_parcelle_pac"' in res.content.decode()
    assert 'name="plantation-connexion_boisement"' not in res.content.decode()


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


def test_hedge_conditions_get_returns_405(client):
    url = reverse("hedge_conditions")
    res = client.get(url, {"department": "44"})
    assert res.status_code == 405


def test_get_conditions_url_removal_mode_returns_empty(client):
    url = reverse("input_hedges", args=["44", "removal"])
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["hedge_conditions_url"] == ""


def test_get_conditions_url_plantation_mode_returns_url_with_params(client):
    url = reverse("input_hedges", args=["44", "plantation"])
    res = client.get(url, {"department": "44", "motif": "autre"})
    assert res.status_code == 200
    conditions_url = res.context["hedge_conditions_url"]
    assert conditions_url.startswith(reverse("hedge_conditions") + "?")
    assert "department=44" in conditions_url
    assert "motif=autre" in conditions_url


def test_get_conditions_url_read_only_with_petition_project(client):
    project = PetitionProjectFactory()
    url = reverse("input_hedges", args=["44", "read_only", project.hedge_data.id])
    res = client.get(url)
    assert res.status_code == 200
    conditions_url = res.context["hedge_conditions_url"]
    assert conditions_url.startswith(reverse("hedge_conditions") + "?")
    assert "department=44" in conditions_url


def test_get_conditions_url_read_only_without_petition_project(client):
    hedge_data = HedgeDataFactory()
    url = reverse("input_hedges", args=["44", "read_only", hedge_data.id])
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["hedge_conditions_url"] == ""


def test_get_conditions_url_read_only_without_hedge_data(client):
    url = reverse("input_hedges", args=["44", "read_only"])
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["hedge_conditions_url"] == ""


def test_hedge_input_post_creates_a_new_snapshot(client):
    """Posting to the id-less url always creates a fresh HedgeData."""
    DCConfigHaieFactory()
    payload = [HedgeFactory().toDict()]
    url = reverse("input_hedges", args=["44", "removal"])

    res = client.post(url, data=json.dumps(payload), content_type="application/json")

    assert res.status_code == 201
    input_id = res.json()["input_id"]
    hedge_data = HedgeData.objects.get(id=input_id)
    assert hedge_data.data[0]["latLngs"] == payload[0]["latLngs"]


def test_hedge_input_post_to_existing_uuid_is_rejected(client):
    """Updating an existing snapshot via its shareable uuid is forbidden."""
    hedge_data = HedgeDataFactory()
    original_data = hedge_data.data
    tampered = [HedgeFactory(length=999).toDict()]
    url = reverse("input_hedges", args=["44", "removal", hedge_data.id])

    res = client.post(url, data=json.dumps(tampered), content_type="application/json")

    assert res.status_code == 405
    hedge_data.refresh_from_db()
    assert hedge_data.data == original_data


class TestStoredXSS:
    """YWH-PGM10356-251: stored XSS via unvalidated HedgeData JSON."""

    XSS_PAYLOAD = "x'><script>alert('XSS')</script><div id='y"

    def test_payload_is_escaped_on_public_page(self, client):
        hedge_data = HedgeDataFactory(
            data=[HedgeFactory(additionalData__note=self.XSS_PAYLOAD).toDict()]
        )
        url = reverse("input_hedges", args=["44", "removal", hedge_data.id])

        res = client.get(url)

        assert res.status_code == 200
        assert b"<script>alert" not in res.content

    def test_payload_is_escaped_on_admin_map(self, admin_client):
        hedge_data = HedgeDataFactory(
            data=[HedgeFactory(additionalData__note=self.XSS_PAYLOAD).toDict()]
        )
        url = reverse("admin:hedges_hedgedata_map", args=[hedge_data.id])

        res = admin_client.get(url)

        assert res.status_code == 200
        assert b"<script>alert" not in res.content

    def test_payload_in_post_is_rejected(self, client):
        """The exact attack from the bug bounty report: only a note field, no valid data."""
        DCConfigHaieFactory()
        entry = HedgeFactory().toDict()
        entry["additionalData"] = {"note": self.XSS_PAYLOAD}
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps([entry]), content_type="application/json"
        )

        assert res.status_code == 400

    def test_unknown_additional_data_keys_are_stripped(self, client):
        DCConfigHaieFactory()
        payload = [HedgeFactory(additionalData__injected_key="malicious").toDict()]
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

        assert res.status_code == 201
        stored = HedgeData.objects.get(id=res.json()["input_id"])
        assert "injected_key" not in stored.data[0]["additionalData"]

    def test_invalid_type_haie_is_rejected(self, client):
        DCConfigHaieFactory()
        payload = [HedgeFactory(additionalData__type_haie="not_a_real_type").toDict()]
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

        assert res.status_code == 400

    def test_invalid_hedge_type_is_rejected(self, client):
        DCConfigHaieFactory()
        entry = HedgeFactory().toDict()
        entry["type"] = "INVALID"
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps([entry]), content_type="application/json"
        )

        assert res.status_code == 400

    def test_invalid_latlngs_is_rejected(self, client):
        DCConfigHaieFactory()
        entry = HedgeFactory().toDict()
        entry["latLngs"] = "not a list"
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps([entry]), content_type="application/json"
        )

        assert res.status_code == 400

    def test_absent_booleans_are_normalized_to_false(self, client):
        DCConfigHaieFactory()
        entry = HedgeFactory().toDict()
        del entry["additionalData"]["sur_parcelle_pac"]
        del entry["additionalData"]["vieil_arbre"]
        url = reverse("input_hedges", args=["44", "removal"])

        res = client.post(
            url, data=json.dumps([entry]), content_type="application/json"
        )

        assert res.status_code == 201
        stored = HedgeData.objects.get(id=res.json()["input_id"])
        stored_additional = stored.data[0]["additionalData"]
        assert stored_additional["sur_parcelle_pac"] is False
        assert stored_additional["vieil_arbre"] is False
