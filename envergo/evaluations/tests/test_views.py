from unittest.mock import patch

import pytest
from django.urls import reverse

from envergo.evaluations.models import Request
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def eval_request_data():
    data = {
        "address": "11B rue Barnier 34110 Vic la Gardiole",
        "parcel-TOTAL_FORMS": "1",
        "parcel-INITIAL_FORMS": "0",
        "parcel-MIN_NUM_FORMS": "0",
        "parcel-MAX_NUM_FORMS": "1000",
        "parcel-0-commune": "34333",
        "parcel-0-section": "BV",
        "parcel-0-prefix": "000",
        "parcel-0-order": "68",
        "application_number": "PC04412321D0123",
        "created_surface": "250",
        "existing_surface": "100",
        "contact_email": "toto@tata.com",
        "project_sponsor_emails": "toto1@tata.com,toto2@tata.com,toto3@tata.com",
        "project_sponsor_phone_number": "0612345678",
        "send_eval_to_sponsor": True,
    }
    return data


def test_searching_inexisting_eval(client):
    """Searching an eval that does not exist returns an error message."""

    search_url = reverse("evaluation_search")
    reference = "PC05112321D0123"
    res = client.post(search_url, data={"reference": reference}, follow=True)
    assert res.status_code == 404

    content = res.content.decode("utf-8")
    assert (
        "l'évaluation Loi sur l'eau n'est pas encore disponible pour ce projet"
        in content
    )


def test_search_existing_eval(client, evaluation):
    """Searching for an eval links to it."""

    search_url = reverse("evaluation_search")
    res = client.post(
        search_url,
        data={"reference": evaluation.reference},
        follow=True,
    )
    assert res.status_code == 200

    content = res.content.decode("utf-8")
    assert "<h1>Notification Loi sur l'eau</h1>" in content


def test_eval_request_wizard_step_1(client):
    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    DATA_KEY = "REQUEST_WIZARD_DATA"
    session = client.session
    assert DATA_KEY in session

    data = session[DATA_KEY]
    assert data["address"][0] == "42 rue du Test, Testville"


def test_eval_request_wizard_step_2(client):

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "contact_email": "contact@example.org",
        "project_sponsor_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_sponsor_phone_number": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    DATA_KEY = "REQUEST_WIZARD_DATA"
    session = client.session
    assert DATA_KEY in session

    data = session[DATA_KEY]
    assert data["project_description"] == ["Bla bla bla"]
    assert qs.count() == 0


@patch("envergo.utils.mattermost.requests.post")
def test_eval_wizard_all_steps(mock_post, settings, client, mailoutbox):
    settings.MATTERMOST_ENDPOINT = "https://example.org/mattermost-endpoint/"

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "contact_email": "contact@example.org",
        "project_sponsor_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_sponsor_phone_number": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    assert qs.count() == 1
    mock_post.assert_called_once()
    assert len(mailoutbox) == 1


def test_dashboard_displays_empty_messages(user, client):
    dashboard_url = reverse("dashboard")
    client.force_login(user)
    res = client.get(dashboard_url)

    assert res.status_code == 200
    assert "aucune demande d'évaluation en attente" in res.content.decode()
    assert "aucune évaluation disponible pour l'instant" in res.content.decode()


def test_dashboard_lists_requests_and_evals(user, client):
    RequestFactory.create_batch(7, contact_email=user.email)
    EvaluationFactory.create_batch(11, contact_email=user.email)

    dashboard_url = reverse("dashboard")
    client.force_login(user)
    res = client.get(dashboard_url)
    content = res.content.decode()

    assert res.status_code == 200
    assert content.count('<tr class="request">') == 7
    assert content.count('<tr class="evaluation">') == 11


def dashboard_does_not_list_other_evals(user, client):
    RequestFactory.create_batch(7)
    EvaluationFactory.create_batch(11)

    dashboard_url = reverse("dashboard")
    client.force_login(user)
    res = client.get(dashboard_url)
    content = res.content.decode()

    assert res.status_code == 200
    assert content.count('<tr class="request">') == 0
    assert content.count('<tr class="evaluation">') == 0


def test_users_can_see_dashboard_menu(user, client):
    client.force_login(user)
    home_url = reverse("home")
    res = client.get(home_url, follow=True)

    assert res.status_code == 200
    assert "Tableau de bord" in res.content.decode()


def test_anonymous_cannot_see_dashboard_menu(client):
    home_url = reverse("home")
    res = client.get(home_url, follow=True)

    assert res.status_code == 200
    assert "Tableau de bord" not in res.content.decode()
