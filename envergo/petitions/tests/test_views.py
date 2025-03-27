from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings
from django.urls import reverse

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    PetitionProjectFactory,
)
from envergo.petitions.views import (
    PetitionProjectCreate,
    PetitionProjectCreationAlert,
    PetitionProjectInstructorView,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.post")
@patch("envergo.petitions.views.reverse")
def test_pre_fill_demarche_simplifiee(mock_reverse, mock_post):
    mock_reverse.return_value = "http://haie.local:3000/projet/ABC123"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "dossier_url": "demarche_simplifiee_url",
        "state": "prefilled",
        "dossier_id": "RG9zc2llci0yMTA3NTY2NQ==",
        "dossier_number": 21075665,
        "dossier_prefill_token": "W3LFL68vStyL62kRBdJSGU1f",
    }
    ConfigHaieFactory()

    view = PetitionProjectCreate()
    factory = RequestFactory()
    request = factory.get("")
    view.request = request
    request.alerts = PetitionProjectCreationAlert(request)

    petition_project = PetitionProjectFactory()
    demarche_simplifiee_url, dossier_number = view.pre_fill_demarche_simplifiee(
        petition_project
    )

    assert demarche_simplifiee_url == "demarche_simplifiee_url"
    assert dossier_number == 21075665

    # Assert the body of the requests.post call
    expected_body = {
        "champ_123": "Autre (collectivité, aménageur, gestionnaire de réseau, "
        "particulier, etc.)",
        "champ_321": "ABC123",
        "champ_456": None,  # improve this test by configuring a result for bcae8
        "champ_654": "http://haie.local:3000/simulateur/resultat/?profil=autre&motif=autre&reimplantation=non"
        "&haies=4406e311-d379-488f-b80e-68999a142c9d&department=44&travaux=destruction&element=haie",
        "champ_789": "http://haie.local:3000/projet/ABC123",
    }
    mock_post.assert_called_once()
    assert mock_post.call_args[1]["json"] == expected_body


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
@patch("requests.post")
@patch("envergo.petitions.views.reverse")
def test_pre_fill_demarche_simplifiee_not_enabled(mock_reverse, mock_post, caplog):
    mock_reverse.return_value = "http://haie.local:3000/projet/ABC123"
    ConfigHaieFactory()

    view = PetitionProjectCreate()
    factory = RequestFactory()
    request = factory.get("")
    view.request = request
    request.alerts = PetitionProjectCreationAlert(request)

    petition_project = PetitionProjectFactory()
    demarche_simplifiee_url, dossier_number = view.pre_fill_demarche_simplifiee(
        petition_project
    )
    assert (
        len(
            [
                rec.message
                for rec in caplog.records
                if "Demarches Simplifiees is not enabled" in rec.message
            ]
        )
        > 0
    )
    assert demarche_simplifiee_url is None
    assert dossier_number is None


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_instructor_view_requires_authentication(haie_user, site):

    ConfigHaieFactory()
    project = PetitionProjectFactory()
    factory = RequestFactory()
    request = factory.get(
        reverse(
            "petition_project_instructor_view", kwargs={"reference": project.reference}
        )
    )

    # Simulate an unauthenticated user
    request.user = AnonymousUser()
    request.site = site
    request.session = {}

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # Simulate an authenticated user
    request.user = haie_user

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response status code is 200 (OK)
    assert response.status_code == 200


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_instructor_dossier_ds_view_requires_authentication(
    haie_user, site
):

    ConfigHaieFactory()
    project = PetitionProjectFactory()
    factory = RequestFactory()
    request = factory.get(
        reverse(
            "petition_project_instructor_dossier_ds_view",
            kwargs={"reference": project.reference},
        )
    )

    # Simulate an unauthenticated user
    request.user = AnonymousUser()
    request.site = site
    request.session = {}

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # Simulate an authenticated user
    request.user = haie_user

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response status code is 200 (OK)
    assert response.status_code == 200


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.post")
@patch("envergo.utils.mattermost.notify")
def test_petition_project_instructor_display_dossier_ds_info(
    mock_post, mock_notify, client, haie_user, site
):
    """Test if dossier data is in template"""
    ConfigHaieFactory()
    project = PetitionProjectFactory()
    instructor_ds_url = reverse(
        "petition_project_instructor_dossier_ds_view",
        kwargs={"reference": project.reference},
    )
    client.user = haie_user
    response = client.post(instructor_ds_url)

    assert response is not None
