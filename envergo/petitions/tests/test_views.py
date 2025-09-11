import html
import re
from unittest.mock import ANY, Mock, patch
from urllib.parse import parse_qs, urlparse

import factory
import pytest
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from envergo.analytics.models import Event
from envergo.geodata.conftest import france_map, loire_atlantique_map  # noqa
from envergo.geodata.tests.factories import Department34Factory, DepartmentFactory
from envergo.hedges.models import TO_PLANT
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.petitions.models import DOSSIER_STATES, InvitationToken
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    GET_DOSSIER_FAKE_RESPONSE,
    GET_DOSSIER_MESSAGES_0_FAKE_RESPONSE,
    GET_DOSSIER_MESSAGES_FAKE_RESPONSE,
    InvitationTokenFactory,
    PetitionProject34Factory,
    PetitionProjectFactory,
)
from envergo.petitions.views import (
    PetitionProjectCreate,
    PetitionProjectCreationAlert,
    PetitionProjectInstructorView,
)
from envergo.users.models import User
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def inactive_haie_user_44() -> User:
    """Haie user with dept 44"""
    haie_user_44 = UserFactory(
        access_amenagement=False,
        access_haie=True,
        is_active=False,
    )
    department_44 = DepartmentFactory.create()
    haie_user_44.departments.add(department_44)
    return haie_user_44


@pytest.fixture
def instructor_haie_user_44() -> User:
    """Haie user with dept 44"""
    instructor_haie_user_44 = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
    )
    department_44 = DepartmentFactory.create()
    instructor_haie_user_44.departments.add(department_44)
    return instructor_haie_user_44


@pytest.fixture()
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=loire_atlantique_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def ep_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


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

    config = ConfigHaieFactory()
    config.demarche_simplifiee_pre_fill_config.append(
        {"id": "abc", "value": "plantation_adequate"}
    )
    config.demarche_simplifiee_pre_fill_config.append(
        {"id": "def", "value": "sur_talus_d"}
    )
    config.demarche_simplifiee_pre_fill_config.append(
        {"id": "ghi", "value": "sur_talus_p"}
    )
    config.save()

    view = PetitionProjectCreate()
    factory = RequestFactory()
    request = factory.get("")
    view.request = request
    request.alerts = PetitionProjectCreationAlert(request)

    hedge_to_plant = HedgeFactory(type=TO_PLANT, additionalData__sur_talus=True)
    hedge_data = HedgeDataFactory()
    hedge_data.data = [hedge_to_plant.toDict()]

    petition_project = PetitionProjectFactory(hedge_data=hedge_data)
    demarche_simplifiee_url, dossier_number = view.pre_fill_demarche_simplifiee(
        petition_project
    )

    assert demarche_simplifiee_url == "demarche_simplifiee_url"
    assert dossier_number == 21075665

    # Assert the body of the requests.post call
    expected_body = {
        "champ_123": None,
        "champ_321": "ABC123",
        "champ_456": None,  # improve this test by configuring a result for bcae8
        "champ_654": ANY,
        "champ_789": "http://haie.local:3000/projet/ABC123",
        "champ_abc": "true",
        "champ_def": "false",
        "champ_ghi": "true",
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
@patch("requests.post")
def test_petition_project_detail(mock_post, client, site):
    """Test consultation view"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = GET_DOSSIER_FAKE_RESPONSE

    mock_post.return_value = mock_response

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    petition_project_url = reverse(
        "petition_project",
        kwargs={"reference": project.reference},
    )

    response = client.get(petition_project_url)
    assert response.status_code == 200
    assert "moulinette" in response.context


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_instructor_view_requires_authentication(
    haie_user,
    inactive_haie_user_44,
    instructor_haie_user_44,
    admin_user,
    site,
):
    """
    Test petition project instructor page requires authentication
    User must be authenticated, haie user, and project department must be in user departments permissions
    """

    ConfigHaieFactory()
    project = PetitionProjectFactory()
    factory = RequestFactory()
    request = factory.get(
        reverse(
            "petition_project_instructor_view", kwargs={"reference": project.reference}
        )
    )
    request.site = site
    request.session = {}

    # Add support  django messaging framework
    request._messages = messages.storage.default_storage(request)

    # Simulate an unauthenticated user
    request.user = AnonymousUser()

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # Simulate an authenticated user, by default no departments
    request.user = haie_user

    response = PetitionProjectInstructorView.as_view()(
        request, reference=project.reference
    )

    # Check that the response status code is 403
    assert response.status_code == 403
    assert response.template_name == "haie/petitions/403.html"

    # Simulate an authenticated user, with department 44, same as project, but not instructor
    request.user = inactive_haie_user_44

    response = PetitionProjectInstructorView.as_view()(
        request,
        reference=project.reference,
    )

    # Check that the response status code is 403
    assert response.status_code == 403

    # Simulate instructor user with department 44
    request.user = instructor_haie_user_44
    response = PetitionProjectInstructorView.as_view()(
        request,
        reference=project.reference,
    )

    # Check that the response status code is 200
    assert response.status_code == 200

    # Simulate admin user, should be autorised
    request.user = admin_user

    response = PetitionProjectInstructorView.as_view()(
        request,
        reference=project.reference,
    )

    # Check that the response status code is 200 (OK)
    assert response.status_code == 200

    # Simulate instructor user with invitation token, should be authorized
    request.user = haie_user
    InvitationTokenFactory(user=haie_user, petition_project=project)
    response = PetitionProjectInstructorView.as_view()(
        request,
        reference=project.reference,
    )

    # Check that the response status code is 403
    assert response.status_code == 200


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_notes_view(
    mock_post, instructor_haie_user_44, client, site
):
    """
    Test petition project instructor notes view
    """
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()
    instructor_notes_url = reverse(
        "petition_project_instructor_notes_view",
        kwargs={"reference": project.reference},
    )

    # Check that the response status code is 200
    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_notes_url)
    assert response.status_code == 200

    # Submit notes
    assert not Event.objects.filter(category="projet", event="edition_notes").exists()
    response = client.post(
        instructor_notes_url, {"instructor_free_mention": "Note mineure : Fa dièse"}
    )
    assert response.url == instructor_notes_url

    assert Event.objects.filter(category="projet", event="edition_notes").exists()


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_view_reglementation_pages(
    mock_post,
    instructor_haie_user_44,
    haie_user,
    conditionnalite_pac_criteria,
    ep_criteria,
    client,
    site,
):
    """Test instruction pages reglementation menu and content"""

    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    # Test regulation imaginaire url
    instructor_url = reverse(
        "petition_project_instructor_regulation_view",
        kwargs={
            "reference": project.reference,
            "regulation": "lutins_elfes_fees_protegees",
        },
    )

    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_url)
    assert response.status_code == 404

    # Test existing regulation url
    instructor_url = reverse(
        "petition_project_instructor_regulation_view",
        kwargs={"reference": project.reference, "regulation": "conditionnalite_pac"},
    )

    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_url)
    assert response.status_code == 200
    assert f"{ep_criteria[0].regulation}" in response.content.decode()

    content = response.content.decode()
    assert "Acceptabilité de la plantation" in content
    assert "Maintien des haies PAC" in content
    assert "Réponse du simulateur" in content

    # Test ep regulation url
    instructor_url = reverse(
        "petition_project_instructor_regulation_view",
        kwargs={"reference": project.reference, "regulation": "ep"},
    )
    # Submit onagre
    response = client.post(instructor_url, {"onagre_number": "1234567"})
    assert response.url == instructor_url
    project.refresh_from_db()
    assert project.onagre_number == "1234567"

    # WHEN I post some instructor data as an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.post(
        instructor_url,
        {
            "onagre_number": "7654321",
        },
    )

    # THEN i should get a 403 forbidden response
    assert response.status_code == 403
    project.refresh_from_db()
    assert project.onagre_number == "1234567"


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_display_dossier_ds_info(
    mock_post, instructor_haie_user_44, client, site
):
    """Test if dossier data is in template"""
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    instructor_ds_url = reverse(
        "petition_project_instructor_dossier_complet_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_ds_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "Formulaire détaillé et pièces jointes" in content
    assert "Vous déposez cette demande en tant que :" in content

    assert "Informations saisies par le demandeur" in content
    assert "<strong>Travaux envisagés\xa0:</strong> Destruction" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_messagerie_ds(
    mock_post, instructor_haie_user_44, client, site
):
    """Test messagerie view"""
    mock_post.return_value = GET_DOSSIER_MESSAGES_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    instructor_messagerie_url = reverse(
        "petition_project_instructor_messagerie_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_messagerie_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "Il manque les infos de la PAC" in content
    assert "mer. 2 avril 2025 11h01" in content
    assert "8 messages" in content
    assert "Coriandrum_sativum" in content

    # Test if dossier has zero messages
    mock_post.return_value = GET_DOSSIER_MESSAGES_0_FAKE_RESPONSE["data"]
    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_messagerie_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "0 message" in content

    # Test if dossier is empty
    mock_post.return_value = "null"
    client.force_login(instructor_haie_user_44)
    response = client.get(instructor_messagerie_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "Impossible de récupérer les informations du dossier" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_list(
    inactive_haie_user_44, instructor_haie_user_44, haie_user, admin_user, client, site
):

    ConfigHaieFactory()
    ConfigHaieFactory(department=factory.SubFactory(Department34Factory))
    # Create two projects non draft, one in 34 and one in 44
    project_34 = PetitionProject34Factory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled
    )
    project_44 = PetitionProjectFactory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled
    )
    response = client.get(reverse("petition_project_list"))

    # Check that the response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # Simulate an authenticated inactive user
    client.force_login(inactive_haie_user_44)
    response = client.get(reverse("petition_project_list"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # Simulate an authenticated user instructor
    client.force_login(instructor_haie_user_44)
    response = client.get(reverse("petition_project_list"))

    # Check that the response status code is 200 (ok)
    assert response.status_code == 200

    # Check only project 44 is present
    content = response.content.decode()
    assert project_34.reference not in content
    assert project_44.reference in content

    client.force_login(admin_user)
    response = client.get(reverse("petition_project_list"))
    # Check all project are present
    content = response.content.decode()
    assert project_34.reference in content
    assert project_44.reference in content

    # GIVEN a user with access to haie, no departments but an invitation token
    InvitationTokenFactory(user=haie_user, petition_project=project_34)
    client.force_login(haie_user)

    # WHEN the user accesses the petition project list
    response = client.get(reverse("petition_project_list"))

    # THEN the user should see the project associated with the invitation token
    assert response.status_code == 200
    content = response.content.decode()
    assert project_34.reference in content
    assert project_44.reference not in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_dl_geopkg(client, haie_user, site):
    """Test Geopkg download"""

    ConfigHaieFactory()
    project = PetitionProjectFactory()
    geopkg_url = reverse(
        "petition_project_hedge_data_export",
        kwargs={"reference": project.reference},
    )
    client.force_login(haie_user)
    response = client.get(geopkg_url)
    response.get("Content-Disposition")
    assert (
        f'filename="haies_dossier_{project.demarches_simplifiees_dossier_number}.gpkg"'
        in response.get("Content-Disposition")
    )
    # TODO: check the features


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_invitation_token(
    client, haie_user, instructor_haie_user_44, site
):
    """Test invitation token creation for petition project"""

    ConfigHaieFactory()
    project = PetitionProjectFactory()
    invitation_token_url = reverse(
        "petition_project_invitation_token",
        kwargs={"reference": project.reference},
    )

    # no user loged in
    response = client.post(invitation_token_url)
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url

    # user not authorized
    client.force_login(haie_user)
    response = client.post(invitation_token_url)
    assert response.status_code == 403
    assert (
        "You are not authorized to create an invitation token for this project."
        == response.json()["error"]
    )

    # WHEN the user is an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.post(invitation_token_url)
    # THEN creation is not authorized
    assert response.status_code == 403
    assert (
        "You are not authorized to create an invitation token for this project."
        == response.json()["error"]
    )

    # WHEN the user is a department instructor
    client.force_login(instructor_haie_user_44)
    response = client.post(invitation_token_url)

    # THEN an invitation token is created
    token = InvitationToken.objects.get(created_by=instructor_haie_user_44)
    assert token.created_by == instructor_haie_user_44
    assert token.petition_project == project
    assert token.token in response.json()["invitation_url"]
    event = Event.objects.get(category="projet", event="invitation")
    assert event.metadata["reference"] == project.reference
    assert event.metadata["department"] == "44"


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_accept_invitation(client, haie_user, site):
    """Test accepting an invitation token for a petition project"""
    ConfigHaieFactory()
    invitation = InvitationTokenFactory()
    accept_invitation_url = reverse(
        "petition_project_accept_invitation",
        kwargs={
            "reference": invitation.petition_project.reference,
            "token": invitation.token,
        },
    )

    # no user loged in
    response = client.get(accept_invitation_url)
    assert response.status_code == 302
    assert (
        f"/comptes/connexion/?next=/projet/{invitation.petition_project.reference}/invitations/{invitation.token}/"
        in response.url
    )

    # valid token used by its creator should not be consumed
    client.force_login(invitation.created_by)
    client.get(accept_invitation_url)
    invitation.refresh_from_db()
    assert invitation.user is None

    # valid token
    another_user = UserFactory(access_amenagement=False, access_haie=True)
    client.force_login(another_user)
    client.get(accept_invitation_url)
    invitation.refresh_from_db()
    assert invitation.user == another_user

    # already used token
    another_user_again = UserFactory(access_amenagement=False, access_haie=True)
    client.force_login(another_user_again)
    response = client.get(accept_invitation_url)
    invitation.refresh_from_db()
    assert invitation.user == another_user
    assert response.status_code == 403

    # outdated token
    invitation = InvitationTokenFactory(
        petition_project=invitation.petition_project,
        valid_until=timezone.now() - timezone.timedelta(days=1),
    )
    accept_invitation_url = reverse(
        "petition_project_accept_invitation",
        kwargs={
            "reference": invitation.petition_project.reference,
            "token": invitation.token,
        },
    )
    client.force_login(haie_user)
    response = client.get(accept_invitation_url)
    assert response.status_code == 403

    # unexpected token
    accept_invitation_url = reverse(
        "petition_project_accept_invitation",
        kwargs={
            "reference": invitation.petition_project.reference,
            "token": "something-farfelue",
        },
    )
    client.force_login(haie_user)
    response = client.get(accept_invitation_url)
    assert response.status_code == 403


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_project_instructor_notes_form(
    client, haie_user, instructor_haie_user_44, site
):
    """Post instruction note as different users"""

    # GIVEN a petition project
    ConfigHaieFactory()
    project = PetitionProjectFactory()
    instructor_notes_form_url = reverse(
        "petition_project_instructor_notes_view",
        kwargs={"reference": project.reference},
    )

    # WHEN I post some instructor data without being logged in
    response = client.post(
        instructor_notes_form_url,
        {
            "instructor_free_mention": "Coupez moi ces vieux chênes tétard et mettez moi du thuya à la place",
        },
    )
    # THEN i should be redirected to the login page
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url

    # WHEN I post some instructor data without being authorized
    client.force_login(haie_user)
    response = client.post(
        instructor_notes_form_url,
        {
            "instructor_free_mention": "Coupez moi ces vieux chênes tétard et mettez moi du thuya à la place",
        },
    )

    # THEN i should get a 403 forbidden response
    assert response.status_code == 403

    # WHEN I post some instructor data with as an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.post(
        instructor_notes_form_url,
        {
            "instructor_free_mention": "Coupez moi ces vieux chênes tétard et mettez moi du thuya à la place",
        },
    )

    # THEN i should get a 403 forbidden response
    assert response.status_code == 403
    assert project.onagre_number == ""
    assert project.instructor_free_mention == ""

    # WHEN I post some instructor data with a department instructor
    client.force_login(instructor_haie_user_44)
    response = client.post(
        instructor_notes_form_url,
        {
            "instructor_free_mention": "Coupez moi ces vieux chênes tétard et mettez moi du thuya à la place",
        },
    )
    # THEN it should update the project
    assert response.status_code == 302
    assert response.url == instructor_notes_form_url
    project.refresh_from_db()
    assert (
        project.instructor_free_mention
        == "Coupez moi ces vieux chênes tétard et mettez moi du thuya à la place"
    )


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
def test_petition_project_alternative(client, haie_user, instructor_haie_user_44, site):
    """Test alternative flow for petition project"""
    # GIVEN a petition project
    ConfigHaieFactory()
    project = PetitionProjectFactory()
    alternative_url = reverse(
        "petition_project_instructor_alternative_view",
        kwargs={"reference": project.reference},
    )

    # WHEN We try to fetch the alternative page by no user is logged in
    response = client.get(alternative_url)

    # THEN we should be redirected to the login page
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url

    # WHEN the user is not an instructor
    client.force_login(haie_user)
    response = client.get(alternative_url)

    # THEN we should be redirected to a 403 error page
    assert response.status_code == 403

    # WHEN the user is a department instructor
    client.force_login(instructor_haie_user_44)
    response = client.get(alternative_url)

    # THEN the page is displayed
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Simulation alternative</h2>" in content

    # Find all href attributes in the HTML
    hrefs = re.findall(r'href="([^"]+)"', content)

    alternative_url = None
    for raw_href in hrefs:
        href = html.unescape(raw_href)
        parsed_url = urlparse(href)
        qs = parse_qs(parsed_url.query)
        if qs.get("alternative") == ["true"]:
            # Found the first matching href
            assert href.startswith("/")
            alternative_url = href
            break
    else:
        assert False, "No href with alternative=true found"

    # WHEN the user create an alternative
    res = client.get(alternative_url)

    # THEN the alternative form is displayed
    assert res.status_code == 200
    content = res.content.decode()
    assert "<b>Simulation alternative</b> à la simulation initiale" in content
    assert (
        'var MATOMO_CUSTOM_URL = "http://testserver/simulateur/formulaire/?alternative=true";'
        in content
    )

    # WHEN the user visit the result page of an alternative
    result_url = alternative_url.replace("/formulaire", "/resultat")
    res = client.get(result_url, follow=True)
    # THEN the result page is displayed
    assert res.status_code == 200
    content = res.content.decode()
    assert "<b>Simulation alternative</b> à la simulation initiale" in content
    assert (
        'var MATOMO_CUSTOM_URL = "http://testserver/simulateur/resultat/?alternative=true";'
        in content
    )
    assert "Partager cette page par email" not in content

    # WHEN the user visit the result plantation page of an alternative
    result_url = alternative_url.replace("/formulaire", "/resultat-plantation")
    res = client.get(result_url, follow=True)
    # THEN the result page is displayed
    assert res.status_code == 200
    content = res.content.decode()
    assert "<b>Simulation alternative</b> à la simulation initiale" in content
    assert (
        'var MATOMO_CUSTOM_URL = "http://testserver/simulateur/resultat-plantation/?alternative=true";'
        in content
    )
    assert "Partager cette page par email" not in content
    assert "La demande d'autorisation est prête à être complétée" not in content
    assert "Copier le lien de cette page" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@patch("envergo.petitions.views.notify")
def test_petition_project_procedure(
    mock_notify, client, haie_user, instructor_haie_user_44, site
):
    """Test procedure flow for petition project"""
    # GIVEN a petition project
    ConfigHaieFactory()
    project = PetitionProjectFactory()
    status_url = reverse(
        "petition_project_instructor_procedure_view",
        kwargs={"reference": project.reference},
    )

    # WHEN We try to fetch the status page by no user is logged in
    response = client.get(status_url)

    # THEN we should be redirected to the login page
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url

    # WHEN the user is not an instructor
    client.force_login(haie_user)
    response = client.get(status_url)

    # THEN we should be redirected to a 403 error page
    assert response.status_code == 403

    # WHEN the user is an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.get(status_url)

    # THEN the page is displayed but the edition button is not there
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Procédure</h2>" in content
    assert "Modifier</button>" not in content

    # WHEN the user is a department instructor
    client.force_login(instructor_haie_user_44)
    response = client.get(status_url)

    # THEN the page is displayed and the edition button is there
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Procédure</h2>" in content
    assert "Modifier</button>" in content

    # WHEN the user edit the status
    data = {
        "stage": "clos",
        "result": "sans_suite",
        "stage_update_comment": "aucun retour depuis 15 ans",
        "stage_date": "10/09/2025",
    }
    res = client.post(status_url, data, follow=True)

    # THEN the state is up to date
    assert res.status_code == 200
    project.refresh_from_db()
    assert project.stage == "clos"
    assert project.result == "sans_suite"
    event = Event.objects.get(category="projet", event="modification_etape")
    assert event.metadata["reference"] == project.reference
    assert event.metadata["etape_finale"] == "clos"
    assert event.metadata["resultat_arrivee"] == "sans_suite"
    assert event.metadata["etape_initiale"] == "a_instruire"
    assert event.metadata["resultat_depart"] == "unset"

    assert mock_notify.call_count == 1
    args, kwargs = mock_notify.call_args_list[0]
    assert "### Mise à jour du statut d'un dossier GUH Loire-Atlantique (44)" in args[0]
    assert "haie" in args[1]

    # WHEN the user try to edit the status as an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    res = client.post(status_url, data)

    # THEN he should be redirected to a 403 error page
    assert res.status_code == 403
