from unittest.mock import patch

import pytest
from django.urls import reverse

from envergo.evaluations.models import Request
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory
from envergo.geodata.models import Parcel

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


def test_eval_request_creation(client, eval_request_data):
    """Eval request form works as intended."""

    request_url = reverse("request_evaluation")
    request_qs = Request.objects.all()
    parcel_qs = Parcel.objects.all()

    assert request_qs.count() == 0
    assert parcel_qs.count() == 0

    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 302
    assert request_qs.count() == 1
    assert parcel_qs.count() == 1
    assert request_qs[0].parcels.count() == 1


def test_eval_works_with_extra_parcels(client, eval_request_data):
    """Eval request form needs a parcel."""

    request_url = reverse("request_evaluation")
    request_qs = Request.objects.all()
    parcel_qs = Parcel.objects.all()

    assert request_qs.count() == 0
    assert parcel_qs.count() == 0

    eval_request_data.update(
        {
            "parcel-TOTAL_FORMS": "2",
            "parcel-1-commune": "34333",
            "parcel-1-section": "BV",
            "parcel-1-prefix": "000",
            "parcel-1-order": "0001",
        }
    )

    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 302
    assert request_qs.count() == 1
    assert parcel_qs.count() == 2
    assert request_qs[0].parcels.count() == 2


def test_eval_error_missing_parcel(client, eval_request_data):
    """Eval request form needs a parcel."""

    request_url = reverse("request_evaluation")
    request_qs = Request.objects.all()
    parcel_qs = Parcel.objects.all()

    assert request_qs.count() == 0
    assert parcel_qs.count() == 0

    eval_request_data.update(
        {
            "parcel-0-commune": "",
            "parcel-0-section": "",
            "parcel-0-prefix": "",
            "parcel-0-order": "",
        }
    )

    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 200
    assert request_qs.count() == 0
    assert parcel_qs.count() == 0
    assert "Vous devez fournir une parcelle" in res.content.decode()


def test_eval_error_wrong_sponsor_emails(client, eval_request_data):
    """Eval request form needs valid sponsor emails."""

    request_url = reverse("request_evaluation")
    request_qs = Request.objects.all()
    parcel_qs = Parcel.objects.all()

    assert request_qs.count() == 0
    assert parcel_qs.count() == 0

    eval_request_data.update({"project_sponsor_emails": "toto1@tata.com, toto2"})

    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 200
    assert request_qs.count() == 0
    assert parcel_qs.count() == 0
    assert "adresse n°2 est invalide" in res.content.decode()


@patch("envergo.utils.mattermost.requests.post")
def test_eval_triggers_ping_to_mattermost(
    mock_post, settings, client, eval_request_data
):
    """Requesting an evaluation pings the project team."""

    settings.MATTERMOST_ENDPOINT = "https://example.org/mattermost-endpoint/"
    request_url = reverse("request_evaluation")
    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 302

    mock_post.assert_called_once()


def test_eval_triggers_email_to_requester(client, eval_request_data, mailoutbox):
    """Requesting an evaluation pings the project team."""

    request_url = reverse("request_evaluation")
    res = client.post(request_url, data=eval_request_data)
    assert res.status_code == 302

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
    res = client.get(home_url)

    assert res.status_code == 200
    assert "Tableau de bord" in res.content.decode()


def test_anonymous_cannot_see_dashboard_menu(client):
    home_url = reverse("home")
    res = client.get(home_url)

    assert res.status_code == 200
    assert "Tableau de bord" not in res.content.decode()
