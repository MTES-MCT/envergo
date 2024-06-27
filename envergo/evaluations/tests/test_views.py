from datetime import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils.timezone import get_current_timezone

from envergo.confs.models import Setting
from envergo.evaluations.models import Request
from envergo.evaluations.tests.factories import (
    EvaluationFactory,
    RequestFactory,
    VersionFactory,
)

pytestmark = pytest.mark.django_db


def test_searching_inexisting_eval(client):
    """Searching an eval that does not exist returns an error message."""

    search_url = reverse("evaluation_search")
    reference = "ABCDEF"
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
    redirect_url = res.redirect_chain[0][0]
    assert redirect_url == f"/avis/{evaluation.reference}/"


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
        "send_eval_to_project_owner": True,
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    DATA_KEY = "REQUEST_WIZARD_DATA"
    session = client.session
    assert DATA_KEY in session

    data = session[DATA_KEY]
    assert data["project_description"] == ["Bla bla bla"]
    assert qs.count() == 0


def test_eval_request_wizard_step_2_missing_petitioner_data(client):
    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "contact_emails": ["contact@example.org"],
        "send_eval_to_project_owner": True,
    }
    res = client.post(url, data=data)
    assert res.status_code == 200
    assert "Ce champ est obligatoire" in res.content.decode()

    data["project_owner_emails"] = "petitioner@example.com"
    data["project_owner_phone"] = "0612345678"
    res = client.post(url, data=data)
    assert res.status_code == 302

    DATA_KEY = "REQUEST_WIZARD_DATA"
    session = client.session
    assert DATA_KEY in session

    data = session[DATA_KEY]
    assert data["project_owner_emails"] == ["petitioner@example.com"]
    assert qs.count() == 0


def test_eval_request_wizard_step_2_petitioner(client):
    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "petitioner",
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
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
def test_eval_wizard_step_1_and_2(mock_post, settings, client, mailoutbox):
    """The evalreq is saved but not submitted."""

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
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    # The evalreq is created but not submitted
    assert qs.count() == 1
    evalreq = qs[0]
    assert evalreq.submitted is False

    # Admin and user are not notified yet
    mock_post.assert_not_called()
    assert len(mailoutbox) == 0


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
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    assert qs.count() == 1
    evalreq = qs[0]
    assert evalreq.submitted is False

    url = reverse("request_eval_wizard_step_3", args=[evalreq.reference])
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert res.status_code == 302

    assert len(callbacks) == 1
    mock_post.assert_called_once()
    assert len(mailoutbox) == 1
    assert "Vous recevrez une réponse dans les trois jours ouvrés" in mailoutbox[0].body
    evalreq.refresh_from_db()
    assert evalreq.submitted is True


@patch("envergo.utils.mattermost.requests.post")
def test_eval_wizard_all_steps_with_test_email(
    mock_post, settings, client, mailoutbox, django_capture_on_commit_callbacks
):
    """Test evalreq are not submitted."""

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
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    assert qs.count() == 1
    evalreq = qs[0]
    assert evalreq.submitted is False

    url = reverse("request_eval_wizard_step_3", args=[evalreq.reference])
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert res.status_code == 302

    assert res.status_code == 302
    assert len(callbacks) == 0
    mock_post.assert_not_called()
    assert len(mailoutbox) == 0


@patch("envergo.utils.mattermost.requests.post")
def test_confirmation_email_override(
    mock_post, settings, client, mailoutbox, django_capture_on_commit_callbacks
):
    settings.MATTERMOST_ENDPOINT = "https://example.org/mattermost-endpoint/"

    Setting.objects.create(
        setting="evalreq_confirmation_email_delay_mention",
        value="Vous recevrez une réponse quand les poules auront des dentiers",
    )

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "contact_emails": ["contact@example.org"],
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    qs = Request.objects.all()
    evalreq = qs[0]

    url = reverse("request_eval_wizard_step_3", args=[evalreq.reference])
    with django_capture_on_commit_callbacks(execute=True):
        res = client.post(url, data=data)

    assert res.status_code == 302
    assert len(mailoutbox) == 1
    assert (
        "Vous recevrez une réponse dans les trois jours ouvrés"
        not in mailoutbox[0].body
    )
    assert (
        "Vous recevrez une réponse quand les poules auront des dentiers"
        in mailoutbox[0].body
    )


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


def test_eval_detail_shows_version_content(client):
    """The eval detail page shows the stored evaluation version content."""

    version = VersionFactory(content="This is a version")
    eval = EvaluationFactory(versions=[version])
    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "This is a version" in res.content.decode()
    assert "<h1>Avis réglementaire</h1>" not in res.content.decode()


def test_eval_detail_shows_latest_version_content(client):
    """The eval detail page shows the most recent version content."""

    tz = get_current_timezone()
    versions = [
        VersionFactory(
            content="This is version 1", created_at=datetime(2024, 1, 1, tzinfo=tz)
        ),
        VersionFactory(
            content="This is version 3", created_at=datetime(2024, 1, 3, tzinfo=tz)
        ),
        VersionFactory(
            content="This is version 2", created_at=datetime(2024, 1, 2, tzinfo=tz)
        ),
    ]
    eval = EvaluationFactory(versions=versions)
    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "This is version 3" in res.content.decode()


def test_eval_detail_without_versions_renders_content(client):
    """When there is no existing version, the eval detail page renders the content dynamically."""
    eval = EvaluationFactory(versions=[])
    assert eval.versions.count() == 0

    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "<h1>Avis réglementaire</h1>" in res.content.decode()
