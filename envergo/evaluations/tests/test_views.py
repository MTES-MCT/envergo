from collections import defaultdict
from datetime import datetime
from unittest.mock import PropertyMock, patch

import pytest
from django.core.exceptions import NON_FIELD_ERRORS
from django.db.utils import IntegrityError
from django.urls import reverse
from django.utils.timezone import get_current_timezone

from envergo.analytics.models import Event
from envergo.confs.models import Setting
from envergo.evaluations.models import Request
from envergo.evaluations.tests.factories import (
    EvaluationFactory,
    RequestFactory,
    VersionFactory,
)
from envergo.moulinette.models import ActionToTake
from envergo.moulinette.tests.factories import (
    ActionToTakeFactory,
    ConfigAmenagementFactory,
)


@pytest.fixture()
def unactivated_moulinette_config(loire_atlantique_department):  # noqa
    ConfigAmenagementFactory(
        department=loire_atlantique_department,
        is_activated=False,
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )


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


def test_eval_request_wizard_step_1(client, moulinette_config):

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    DATA_KEY = "REQUEST_WIZARD_DATA"
    session = client.session
    assert DATA_KEY in session

    data = session[DATA_KEY]
    assert data["address"][0] == "42 rue du Test, 44000 Testville"


def test_eval_request_wizard_step_1_unavailable_department(
    client, unactivated_moulinette_config
):

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302
    assert "/indisponible/44" in res.url


def test_eval_request_wizard_step_1_missing_department(client):
    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 200
    res.context_data["form"].has_error(NON_FIELD_ERRORS, "unknown_department")

    error_event = Event.objects.filter(category="erreur", event="formulaire-ar").get()
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "__all__": [
            {
                "code": "unknown_department",
                "message": "Nous ne parvenons pas à situer votre projet. Merci "
                "de saisir quelques caractères et de sélectionner une "
                "option dans la liste.",
            }
        ]
    }
    assert "data" in error_event.metadata
    assert error_event.metadata["data"] == data


def test_eval_request_wizard_step_2(client):
    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": ["contact@example.org"],
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
        "urbanism_department_emails": ["contact@example.org"],
        "send_eval_to_project_owner": True,
    }
    res = client.post(url, data=data)
    assert res.status_code == 200
    assert "Ce champ est obligatoire" in res.content.decode()

    error_event = Event.objects.filter(category="erreur", event="formulaire-ar").get()
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "project_owner_emails": [
            {"code": "required", "message": "Ce champ est obligatoire."}
        ]
    }
    assert "data" in error_event.metadata

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
def test_eval_wizard_step_1_and_2(
    mock_post, settings, client, mailoutbox, moulinette_config
):
    """The evalreq is saved but not submitted."""

    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": ["contact@example.org"],
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
    mock_post,
    settings,
    client,
    mailoutbox,
    django_capture_on_commit_callbacks,
    moulinette_config,
):
    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": ["urbanism@example.org"],
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    assert qs.count() == 1
    evalreq = qs[0]
    assert evalreq.submitted is False

    # WHEN I call the step 3 without the obfuscation key
    url = reverse("request_eval_wizard_step_3", args=[evalreq.reference])
    res = client.post(url, data=data)

    # THEN I get a 404
    assert res.status_code == 404
    assert "Le lien de cette page a expiré." in res.content.decode()

    url = evalreq.upload_files_url
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert res.status_code == 302

    assert len(callbacks) == 2
    mock_post.assert_called_once()
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["urbanism@example.org"]
    assert "Vous recevrez une réponse dans les trois jours ouvrés" in mailoutbox[0].body
    evalreq.refresh_from_db()
    assert evalreq.submitted is True


def test_eval_wizard_request_confirmation_recipient(
    settings,
    client,
    mailoutbox,
    django_capture_on_commit_callbacks,
    moulinette_config,
):
    """When the user is the petitioner, the confirmation email is sent to the project owner."""
    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {
        "address": "42 rue du Test, 44000 Testville",
        "project_description": "Bla bla bla",
    }
    res = client.post(url, data=data)
    url = reverse("request_eval_wizard_step_2")
    data = {
        "user_type": "petitioner",
        "send_eval_to_project_owner": True,
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    evalreq = qs[0]
    url = evalreq.upload_files_url
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert res.status_code == 302

    assert len(callbacks) == 2
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["sponsor1@example.org", "sponsor2@example.org"]


@patch("envergo.utils.mattermost.requests.post")
def test_eval_is_only_submitted_once(
    mock_post,
    settings,
    client,
    mailoutbox,
    django_capture_on_commit_callbacks,
    moulinette_config,
):
    """We only send the notifications once."""

    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": ["contact@example.org"],
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    evalreq = qs[0]
    url = evalreq.upload_files_url
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert len(callbacks) == 2  # first time both on_commit are called

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert len(callbacks) == 1  # second time we call only the "post to automation" task

    mock_post.assert_called_once()
    assert len(mailoutbox) == 1
    evalreq.refresh_from_db()
    assert evalreq.submitted is True


@patch("envergo.utils.mattermost.requests.post")
def test_eval_wizard_all_steps_with_test_email(
    mock_post,
    settings,
    client,
    mailoutbox,
    django_capture_on_commit_callbacks,
    moulinette_config,
):
    """Test evalreq are not submitted."""

    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )
    settings.TEST_EMAIL = "test@test.org"

    qs = Request.objects.all()
    assert qs.count() == 0

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": [settings.TEST_EMAIL],
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    assert qs.count() == 1
    evalreq = qs[0]
    assert evalreq.submitted is False

    url = evalreq.upload_files_url
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        res = client.post(url, data=data)
    assert res.status_code == 302

    assert res.status_code == 302
    assert len(callbacks) == 0
    mock_post.assert_not_called()
    assert len(mailoutbox) == 0


@patch("envergo.utils.mattermost.requests.post")
def test_confirmation_email_override(
    mock_post,
    settings,
    client,
    mailoutbox,
    django_capture_on_commit_callbacks,
    moulinette_config,
):
    settings.MATTERMOST_ENDPOINT_AMENAGEMENT = (
        "https://example.org/mattermost-endpoint/"
    )

    Setting.objects.create(
        setting="evalreq_confirmation_email_delay_mention",
        value="Vous recevrez une réponse quand les poules auront des dentiers",
    )

    url = reverse("request_eval_wizard_step_1")
    data = {"address": "42 rue du Test, 44000 Testville"}
    res = client.post(url, data=data)
    assert res.status_code == 302

    url = reverse("request_eval_wizard_step_2")
    data = {
        "project_description": "Bla bla bla",
        "user_type": "instructor",
        "urbanism_department_emails": ["contact@example.org"],
        "project_owner_emails": "sponsor1@example.org,sponsor2@example.org",
        "project_owner_phone": "0612345678",
    }
    res = client.post(url, data=data)
    assert res.status_code == 302

    qs = Request.objects.all()
    evalreq = qs[0]

    url = evalreq.upload_files_url
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
        7, urbanism_department_emails=[user.email, "someoneelse@example.com"]
    )
    EvaluationFactory.create_batch(
        11, urbanism_department_emails=[user.email, "someoneelse@example.com"]
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
    assert "Mes avis" in res.content.decode()


def test_eval_detail_shows_version_content(client):
    """The eval detail page shows the stored evaluation version content."""

    version = VersionFactory(content="This is a version", published=True)
    eval = EvaluationFactory(versions=[version])
    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "This is a version" in res.content.decode()
    assert "<h1>Avis réglementaire</h1>" not in res.content.decode()


def test_only_published_versions_are_shown(client, moulinette_config):
    """Unpublished versions are not displayed."""

    version = VersionFactory(content="This is a version", published=False)
    eval = EvaluationFactory(versions=[version])
    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "This is a version" not in res.content.decode()
    assert "<h1>Avis réglementaire</h1>" in res.content.decode()
    # assert a visit event is created with the complete result in it
    event = Event.objects.get(category="evaluation", event="visit")
    assert event.metadata.get("main_result")


def test_eval_detail_shows_latest_published_version_content(client):
    """The eval detail page shows the most recent published version content."""

    tz = get_current_timezone()
    versions = [
        VersionFactory(
            content="This is version 1", created_at=datetime(2024, 1, 1, tzinfo=tz)
        ),
        VersionFactory(
            content="This is version 3", created_at=datetime(2024, 1, 3, tzinfo=tz)
        ),
        VersionFactory(
            content="This is version 2",
            created_at=datetime(2024, 1, 2, tzinfo=tz),
            published=True,
        ),
        VersionFactory(
            content="This is version 4", created_at=datetime(2024, 1, 4, tzinfo=tz)
        ),
    ]
    eval = EvaluationFactory(versions=versions)
    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 200
    assert "This is version 2" in res.content.decode()


def test_eval_detail_without_versions_does_not_render_content(client):
    """When there is no existing version, the eval detail page is not available."""
    eval = EvaluationFactory(versions=[])
    assert eval.versions.count() == 0

    url = eval.get_absolute_url()
    res = client.get(url)
    assert res.status_code == 404


def test_only_one_version_can_be_published():
    versions = [
        VersionFactory(content="This is a version", published=True),
        VersionFactory(content="This is a version", published=True),
    ]
    with pytest.raises(IntegrityError):
        EvaluationFactory(versions=versions)


def test_admin_can_view_draft_versions(admin_client):

    published = VersionFactory(content="This is a published version", published=True)
    draft = VersionFactory(content="This is a draft version", published=False)
    eval = EvaluationFactory(versions=[published, draft])
    url = eval.get_absolute_url()
    version_url = f"{url}?version={draft.pk}"
    res = admin_client.get(version_url)
    assert res.status_code == 200
    assert "This is a draft version" in res.content.decode()
    assert "This is a published version" not in res.content.decode()


def test_admin_can_view_current_content(admin_client):
    """Admin can preview a specific version."""

    published = VersionFactory(content="This is a published version", published=True)
    draft = VersionFactory(content="This is a draft version", published=False)
    eval = EvaluationFactory(versions=[published, draft])
    url = eval.get_absolute_url()
    version_url = f"{url}?version={draft.pk}"
    res = admin_client.get(version_url)
    assert res.status_code == 200
    assert "This is a draft version" in res.content.decode()
    assert "This is a published version" not in res.content.decode()


def test_users_cannot_view_draft_versions(client):
    """Users trying to view a custom version get a 404."""

    published = VersionFactory(content="This is a published version", published=True)
    draft = VersionFactory(content="This is a draft version", published=False)
    eval = EvaluationFactory(versions=[published, draft])
    url = eval.get_absolute_url()
    version_url = f"{url}?version={draft.pk}"
    res = client.get(version_url)
    assert res.status_code == 403


def test_admin_can_view_unpublished_content(admin_client):

    published = VersionFactory(content="This is a published version", published=True)
    draft = VersionFactory(content="This is a draft version", published=False)
    eval = EvaluationFactory(versions=[published, draft])
    url = eval.get_absolute_url()
    version_url = f"{url}?preview"
    res = admin_client.get(version_url)
    assert res.status_code == 200
    assert "This is a draft version" not in res.content.decode()
    assert "This is a published version" not in res.content.decode()
    assert "<h1>Avis réglementaire</h1>" in res.content.decode()


@patch(
    "envergo.moulinette.models.Moulinette.actions_to_take", new_callable=PropertyMock
)
def test_actions_to_take_are_displayed_in_evaluations(mock_actions_to_take, client):
    # GIVEN an evaluation with display_actions_to_take set to True
    # and ActionToTake records exist in the DB
    ActionToTakeFactory(slug="mention_arrete_lse")
    ActionToTakeFactory(slug="etude_zh_lse", target="petitioner")
    eval = EvaluationFactory(display_actions_to_take=True)
    url = eval.get_absolute_url()
    actions = ActionToTake.objects.all()
    actions_dict = defaultdict(list)
    for action in actions:
        action_key = action.type if action.type == "pc" else action.target
        actions_dict[action_key].append(action)

    mock_actions_to_take.return_value = actions_dict

    # WHEN I display the evaluation detail page
    res = client.get(url)
    assert res.status_code == 200
    assert "<h1>Avis réglementaire</h1>" in res.content.decode()

    # THEN I see the actions to take section
    assert "Actions à mener" in res.content.decode()
    assert 'id="action-mention_arrete_lse"' in res.content.decode()
    assert 'id="action-etude_zh_lse"' in res.content.decode()
