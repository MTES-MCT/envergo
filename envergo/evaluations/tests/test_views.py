from unittest.mock import patch

import pytest
from django.urls import reverse

from envergo.evaluations.models import Request
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory

pytestmark = pytest.mark.django_db


def test_searching_inexisting_eval(client):
    """Searching an eval that does not exist returns an error message."""

    search_url = reverse("evaluation_search")
    reference = "PC05112321D0123"
    res = client.post(search_url, data={"reference": reference}, follow=True)
    assert res.status_code == 404

    content = res.content.decode("utf-8")
    assert (
        "l'avis réglementaire correspondant à cette référence est introuvable"
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
        "user_type": "instructor",
        "contact_emails": ["contact@example.org"],
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


def test_eval_request_wizard_step_2_petitioner(client):
    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "petitioner",
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
def test_eval_wizard_all_steps(
    mock_post, settings, client, mailoutbox, django_capture_on_commit_callbacks
):
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
        "user_type": "instructor",
        "contact_emails": ["contact@example.org"],
        "project_sponsor_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_sponsor_phone_number": "0612345678",
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)

    assert res.status_code == 302
    assert len(callbacks) == 1
    assert qs.count() == 1
    mock_post.assert_called_once()
    assert len(mailoutbox) == 1


@patch("envergo.utils.mattermost.requests.post")
def test_eval_wizard_all_steps_with_test_email(
    mock_post, settings, client, mailoutbox, django_capture_on_commit_callbacks
):
    settings.MATTERMOST_ENDPOINT = "https://example.org/mattermost-endpoint/"
    settings.TEST_EMAIL = "test@test.org"

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "contact_emails": [settings.TEST_EMAIL],
        "project_sponsor_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_sponsor_phone_number": "0612345678",
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)

    assert res.status_code == 302
    assert len(callbacks) == 0
    assert qs.count() == 1
    mock_post.assert_not_called()
    assert len(mailoutbox) == 0


def test_dashboard_displays_empty_messages(user, client):
    dashboard_url = reverse("dashboard")
    client.force_login(user)
    res = client.get(dashboard_url)

    assert res.status_code == 200
    assert "aucune demande d'avis réglementaire en attente" in res.content.decode()
    assert "aucun avis réglementaire disponible pour l'instant" in res.content.decode()


def test_dashboard_lists_requests_and_evals(user, client):
    RequestFactory.create_batch(
        7, contact_emails=[user.email, "someoneelse@example.com"]
    )
    EvaluationFactory.create_batch(
        11, contact_emails=[user.email, "someoneelse@example.com"]
    )

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


def test_share_evaluation_by_email_form_for_anonymous(client, evaluation, mailoutbox):
    """Anonymous users cannot share by email."""

    url = evaluation.get_absolute_url()
    res = client.get(url)
    content = res.content.decode()

    assert "Partagez cet avis réglementaire" in content
    assert (
        '<button class="fr-btn fr-btn--icon-left fr-fi-mail-line" type="submit">Partager par email</button>'
        not in content
    )
    assert (
        '<input type="text" name="emails" class=" fr-input" required disabled id="id_emails">'
        in content
    )

    res = client.post(url, data={"emails": "test@example.org"})
    assert res.status_code == 405  # method not allowed
    assert len(mailoutbox) == 0


def test_share_evaluation_by_email_form(client, user, evaluation, mailoutbox):
    """Anonymous users cannot share by email."""

    client.force_login(user)

    url = evaluation.get_absolute_url()
    res = client.get(url)
    content = res.content.decode()

    assert "Partagez cet avis réglementaire" in content
    assert (
        '<button class="fr-btn fr-btn--icon-left fr-fi-mail-line" type="submit">Partager par email</button>'
        in content
    )
    assert (
        '<input type="text" name="emails" class=" fr-input" required id="id_emails">'
        in content
    )

    res = client.post(url, data={"emails": "test@example.org"})
    assert res.status_code == 302
    assert len(mailoutbox) == 1
