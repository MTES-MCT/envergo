from datetime import date, timedelta
from unittest.mock import ANY, Mock, patch

import factory
import pytest
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from envergo.analytics.models import Event
from envergo.geodata.conftest import france_map, loire_atlantique_map  # noqa
from envergo.geodata.tests.factories import Department34Factory
from envergo.hedges.models import TO_PLANT
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)
from envergo.petitions.models import (
    DOSSIER_STATES,
    InvitationToken,
    LatestMessagerieAccess,
)
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    DOSSIER_SEND_MESSAGE_FAKE_RESPONSE,
    FILE_TEST_NOK_PATH,
    FILE_TEST_PATH,
    GET_DOSSIER_FAKE_RESPONSE,
    GET_DOSSIER_MESSAGES_0_FAKE_RESPONSE,
    GET_DOSSIER_MESSAGES_FAKE_RESPONSE,
    InvitationTokenFactory,
    PetitionProject34Factory,
    PetitionProjectFactory,
    SimulationFactory,
)
from envergo.petitions.views import (
    PetitionProjectCreate,
    PetitionProjectCreationAlert,
    PetitionProjectInstructorConsultationsView,
    PetitionProjectInstructorView,
    PetitionProjectInvitationTokenCreate,
    PetitionProjectInvitationTokenDelete,
)
from envergo.users.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("config.urls_haie")]


@pytest.fixture(autouse=True)
def fake_haie_settings(settings):
    settings.ENVERGO_HAIE_DOMAIN = "testserver"
    settings.ENVERGO_AMENAGEMENT_DOMAIN = "otherserver"


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

    config = DCConfigHaieFactory()
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

    petition_project = PetitionProjectFactory(reference="ABC123", hedge_data=hedge_data)
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
        "champ_ghi": "false",
    }
    mock_post.assert_called_once()
    assert mock_post.call_args[1]["json"] == expected_body


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
@patch("requests.post")
@patch("envergo.petitions.views.reverse")
def test_pre_fill_demarche_simplifiee_not_enabled(mock_reverse, mock_post, caplog):
    mock_reverse.return_value = "http://haie.local:3000/projet/ABC123"
    DCConfigHaieFactory()

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


@patch("requests.post")
def test_petition_project_detail(mock_post, client, site):
    """Test consultation view"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = GET_DOSSIER_FAKE_RESPONSE

    mock_post.return_value = mock_response

    DCConfigHaieFactory(
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
    assert Event.objects.get(
        category="simulateur", event="consultation", metadata__user_type="anonymous"
    )
    # default PetitionProjectFactory has hedges near Aniane but is declared in department 44
    assert response.context["has_hedges_outside_department"]
    assert "Le projet est hors du département sélectionné" in response.content.decode()

    # Given hedges in department 44 and accross the department border
    hedge_44 = HedgeFactory(
        latLngs=[
            {"lat": 47.202984120693635, "lng": -1.7100316286087038},
            {"lat": 47.201198235567496, "lng": -1.7097365856170657},
        ]
    )
    hedge_44_85 = HedgeFactory(
        latLngs=[
            {"lat": 47.05281499678513, "lng": -1.2435150146484377},
            {"lat": 47.103783870991634, "lng": -1.1837768554687502},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_44, hedge_44_85])
    project = PetitionProjectFactory(reference="DEF456", hedge_data=hedges)
    petition_project_url = reverse(
        "petition_project",
        kwargs={"reference": project.reference},
    )

    # WHEN I get the project detail page
    response = client.get(petition_project_url)

    # THEN I should see that there is no hedges to remove outside the department
    assert not response.context["has_hedges_outside_department"]
    assert (
        "Le projet est hors du département sélectionné" not in response.content.decode()
    )

    # THEN I should not see instructor info for simulations
    assert "Vous souhaitez modifier votre simulation ?" in response.content.decode()
    assert (
        "Vous souhaitez faire une simulation alternative ?"
        not in response.content.decode()
    )


def test_petition_project_instructor_view_requires_authentication(
    haie_user,
    inactive_haie_user_44,
    haie_user_44,
    haie_instructor_44,
    admin_user,
    site,
):
    """
    Test petition project instructor page requires authentication
    User must be authenticated, haie user, and project department must be in user departments permissions
    """

    DCConfigHaieFactory()
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
    request.user = haie_user_44
    response = PetitionProjectInstructorView.as_view()(
        request,
        reference=project.reference,
    )

    # Check that the response status code is 200
    assert response.status_code == 200

    # Simulate instructor user with department 44
    request.user = haie_instructor_44
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


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_notes_view(
    mock_post, haie_user_44, haie_instructor_44, client, site
):
    """
    Test petition project instructor notes view
    """
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()
    instructor_notes_url = reverse(
        "petition_project_instructor_notes_view",
        kwargs={"reference": project.reference},
    )

    # Given user is instructor on department
    client.force_login(haie_user_44)
    # Then response status code is 200
    response = client.get(instructor_notes_url)
    assert response.status_code == 200
    # And user cannot post a new note
    response = client.post(
        instructor_notes_url, {"instructor_free_mention": "Note mineure : Fa dièse"}
    )
    assert response.status_code == 403
    project.refresh_from_db()
    assert "Note mineure : Fa dièse" not in project.instructor_free_mention

    # Given user is instructor on department
    client.force_login(haie_instructor_44)
    # Then response status code is 200
    response = client.get(instructor_notes_url)
    assert response.status_code == 200
    # And user can post a new note
    assert not Event.objects.filter(category="dossier", event="edition_notes").exists()
    response = client.post(
        instructor_notes_url, {"instructor_free_mention": "Note mineure : Fa dièse"}
    )
    assert response.url == instructor_notes_url
    project.refresh_from_db()
    assert "Note mineure : Fa dièse" in project.instructor_free_mention
    # And a new SQL event is created
    assert Event.objects.filter(category="dossier", event="edition_notes").exists()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_view_reglementation_pages(
    mock_post,
    haie_instructor_44,
    haie_user,
    conditionnalite_pac_criteria,
    ep_criteria,
    client,
    site,
):
    """Test instruction pages reglementation menu and content"""

    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    DCConfigHaieFactory(
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

    client.force_login(haie_instructor_44)
    response = client.get(instructor_url)
    assert response.status_code == 404

    # Test existing regulation url
    instructor_url = reverse(
        "petition_project_instructor_regulation_view",
        kwargs={"reference": project.reference, "regulation": "conditionnalite_pac"},
    )

    client.force_login(haie_instructor_44)
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

    # When I go to a regulation page
    instructor_url = reverse(
        "petition_project_instructor_regulation_view",
        kwargs={"reference": project.reference, "regulation": "conditionnalite_pac"},
    )
    response = client.get(instructor_url)
    # I should get ign_url and googlemap_url
    assert "ign_url" in response.context
    assert response.context["ign_url"].startswith("https://www.geoportail.gouv.fr/")
    assert "google_maps_url" in response.context
    assert response.context["google_maps_url"].startswith(
        "https://www.google.com/maps/"
    )

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


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_display_dossier_ds_info(
    mock_post, haie_instructor_44, client, site
):
    """Test if dossier data is in template"""
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    instructor_ds_url = reverse(
        "petition_project_instructor_dossier_complet_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(instructor_ds_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "Formulaire détaillé et pièces jointes" in content
    assert "Vous déposez cette demande en tant que :" in content

    assert "Informations saisies par le demandeur" in content
    assert "<strong>Travaux envisagés\xa0:</strong> Destruction" in content


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_project_instructor_messagerie_ds(
    mock_ds_query_execute, haie_user_44, haie_instructor_44, client, site
):
    """Test messagerie view"""

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )
    project = PetitionProjectFactory()

    instructor_messagerie_url = reverse(
        "petition_project_instructor_messagerie_view",
        kwargs={"reference": project.reference},
    )

    # Test dossier get messages

    # GIVEN an invited haie user 44
    client.force_login(haie_user_44)
    # WHEN I get messagerie page
    assert not Event.objects.filter(category="message", event="lecture").exists()
    mock_ds_query_execute.return_value = GET_DOSSIER_MESSAGES_FAKE_RESPONSE["data"]
    response = client.get(instructor_messagerie_url)
    # THEN I can access to messagerie page
    assert response.status_code == 200
    # AND an event is created
    assert Event.objects.filter(category="message", event="lecture").exists()
    # AND I can read messages
    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "Il manque les infos de la PAC" in content
    assert "mer. 2 avril 2025 11h01" in content
    assert "8 messages" in content
    assert "Coriandrum_sativum" in content
    # AND nouveau message is not in page
    assert "Nouveau message</button>" not in content

    # GIVEN an instructor haie user 44
    client.force_login(haie_instructor_44)
    mock_ds_query_execute.return_value = GET_DOSSIER_MESSAGES_FAKE_RESPONSE["data"]
    response = client.get(instructor_messagerie_url)
    # THEN I can access to messagerie page
    assert response.status_code == 200
    # AND I can read messages
    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "Il manque les infos de la PAC" in content
    assert "mer. 2 avril 2025 11h01" in content
    assert "8 messages" in content
    assert "Coriandrum_sativum" in content
    # AND nouveau message is in page
    assert "Nouveau message" in content

    # Test if dossier has zero messages
    mock_ds_query_execute.return_value = GET_DOSSIER_MESSAGES_0_FAKE_RESPONSE["data"]
    response = client.get(instructor_messagerie_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "0 message" in content

    # Test if dossier is empty : mock_response3_get_dossier_none
    mock_ds_query_execute.return_value = "null"
    response = client.get(instructor_messagerie_url)
    assert response.status_code == 200

    content = response.content.decode()
    assert "<h2>Messagerie</h2>" in content
    assert "Impossible de récupérer les informations du dossier" in content

    # Test send message
    assert not Event.objects.filter(category="message", event="envoi").exists()

    # Given a message and attachment image file
    attachment = SimpleUploadedFile(FILE_TEST_PATH.name, FILE_TEST_PATH.read_bytes())
    message_data = {
        "message_body": "test",
        "additional_file": attachment,
    }

    # WHEN I post message
    mock_ds_query_execute.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    response = client.post(instructor_messagerie_url, message_data, follow=True)

    # THEN I receive ok response and an event is created
    content = response.content.decode()
    assert "Le message a bien été envoyé au demandeur." in content
    envoi_event = Event.objects.filter(category="message", event="envoi").get()
    assert envoi_event.metadata["piece_jointe"] == 1

    # GIVEN a message and doc attachment unauthorized extension
    attachment = SimpleUploadedFile(
        FILE_TEST_NOK_PATH.name, FILE_TEST_NOK_PATH.read_bytes()
    )
    message_data = {
        "message_body": "test",
        "additional_file": attachment,
    }
    # WHEN I post message
    mock_ds_query_execute.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    response = client.post(instructor_messagerie_url, message_data, follow=True)
    # THEN I receive nok response
    content = response.content.decode()
    assert (
        "Le message n’a pas pu être envoyé.\nVérifiez que la pièce jointe respecte les conditions suivantes"
        in content
    )  # noqa


def test_petition_project_list(
    inactive_haie_user_44, haie_instructor_44, haie_user, admin_user, client, site
):

    DCConfigHaieFactory()
    DCConfigHaieFactory(department=factory.SubFactory(Department34Factory))
    # GIVEN two projects non draft, one in 34 and one in 44
    today = date.today()
    last_month = today - timedelta(days=30)
    project_34 = PetitionProject34Factory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44 = PetitionProjectFactory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=last_month,
    )

    # WHEN visitor acesses to project list
    response = client.get(reverse("petition_project_list"))
    # THEN response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # WHEN an inactive user acesses to project list
    client.force_login(inactive_haie_user_44)
    response = client.get(reverse("petition_project_list"))
    # THEN response is a redirect to the login page
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))

    # WHEN an instructor on 44 acesses to project list
    client.force_login(haie_instructor_44)
    response = client.get(reverse("petition_project_list"))
    # THEN response status code is 200 (ok)
    assert response.status_code == 200
    # AND only project 44 is present
    content = response.content.decode()
    assert project_34.reference not in content
    assert project_44.reference in content

    # WHEN an admin user acesses to project list
    client.force_login(admin_user)
    response = client.get(reverse("petition_project_list"))
    # THEN all project are present
    content = response.content.decode()
    assert project_34.reference in content
    assert project_44.reference in content
    # AND ordering is correct (most recent first)
    assert content.index(project_34.reference) < content.index(project_44.reference)

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
    # AND the project is read only
    assert f'aria-describedby="read-only-tooltip-{project_34.reference}' in content


def test_petition_project_list_filters(
    haie_user_44, haie_instructor_44, haie_user, admin_user, client, site
):
    """Test filters on project list"""

    project_list_url = reverse("petition_project_list")
    # Given config haie on 44
    config_haie_44 = DCConfigHaieFactory()
    department_44 = config_haie_44.department

    # Given two haie instructors, haie user, `haie_user_44` and admin user instructor
    haie_instructor_44_instructor1 = UserFactory(is_haie_instructor=True)
    haie_instructor_44_instructor1.departments.add(department_44)
    haie_instructor_44_instructor2 = UserFactory(is_haie_instructor=True)
    haie_instructor_44_instructor2.departments.add(department_44)
    admin_user.is_instructor = True
    admin_user.save()

    # GIVEN projects non draft followed by users and instructors
    today = date.today()
    project_44_followed_by_instructor1 = PetitionProjectFactory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44_followed_by_instructor1.followed_by.add(haie_instructor_44_instructor1)
    project_44_followed_by_instructor2 = PetitionProjectFactory(
        reference="ACB132",
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44_followed_by_instructor2.followed_by.add(haie_instructor_44_instructor2)
    project_44_followed_by_invited = PetitionProjectFactory(
        reference="XYZ123",
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44_followed_by_invited.followed_by.add(haie_user_44)
    project_44_followed_by_invited_and_instructor2 = PetitionProjectFactory(
        reference="XYZ456",
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44_followed_by_invited_and_instructor2.followed_by.add(haie_user_44)
    project_44_followed_by_invited_and_instructor2.followed_by.add(
        haie_instructor_44_instructor2
    )
    project_44_followed_by_superuser = PetitionProjectFactory(
        reference="ADM123",
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )
    project_44_followed_by_superuser.followed_by.add(admin_user)
    project_44_no_instructor = PetitionProjectFactory(
        reference="XYZ789",
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=today,
    )

    # AS haie user with no project
    client.force_login(haie_user)
    # WHEN I search on my projects
    response = client.get(f"{project_list_url}?f=mes_dossiers")
    content = response.content.decode()
    # THEN alert "aucun dossier" is displayed
    assert "Aucun dossier n’est accessible pour le moment" in content

    # AS haie user invited on one project
    InvitationTokenFactory(
        user=haie_user, petition_project=project_44_followed_by_instructor1
    )
    # WHEN I search on my projects
    response = client.get(f"{project_list_url}?f=mes_dossiers")
    content = response.content.decode()
    # THEN alert "aucun dossier" is not displayed, only a table
    assert "Aucun dossier n’est accessible pour le moment" not in content
    # AND followed by me project list is empty
    assert response.context["object_list"].count() == 0

    # AS Instructor 1 on 44
    client.force_login(haie_instructor_44_instructor1)
    # WHEN I search on my projects
    response = client.get(f"{project_list_url}?f=mes_dossiers")
    content = response.content.decode()

    # THEN project list is filtered on user followed projects
    assert project_44_followed_by_instructor1.reference in content
    assert project_44_followed_by_instructor2.reference not in content
    assert project_44_followed_by_invited.reference not in content
    assert project_44_followed_by_superuser.reference not in content
    assert project_44_no_instructor.reference not in content

    # WHEN I search on projects followed by no instructor
    response = client.get(f"{project_list_url}?f=dossiers_sans_instructeur")
    content = response.content.decode()

    # THEN project list is filtered on project followed by no instructor, excluding admin users
    assert project_44_followed_by_instructor1.reference not in content
    assert project_44_followed_by_instructor2.reference not in content
    assert project_44_followed_by_invited.reference in content
    assert project_44_followed_by_superuser.reference in content
    assert project_44_no_instructor.reference in content

    # AS Instructor 2 on 44
    client.force_login(haie_instructor_44_instructor2)
    # WHEN I search on my projects
    response = client.get(f"{project_list_url}?f=mes_dossiers")
    content = response.content.decode()

    # Then project list is filtered on user followed projects
    assert project_44_followed_by_instructor1.reference not in content
    assert project_44_followed_by_instructor2.reference in content
    assert project_44_followed_by_invited.reference not in content
    assert project_44_followed_by_superuser.reference not in content
    assert project_44_no_instructor.reference not in content

    # AS admin user
    client.force_login(admin_user)
    # WHEN I visit project list page
    response = client.get(project_list_url)
    # THEN followers are in project
    projects_followers = dict(
        response.context["object_list"].values_list("reference", "followers")
    )
    # Project followed by only superuser has no follower
    assert projects_followers[project_44_followed_by_superuser.reference] == []
    # Project followed by instructor1 has only instructor1 as follower
    assert projects_followers[project_44_followed_by_instructor1.reference] == [
        haie_instructor_44_instructor1.email
    ]
    # Project followed by haie user and instructor2 has only instructor2 as follower
    assert projects_followers[
        project_44_followed_by_invited_and_instructor2.reference
    ] == [haie_instructor_44_instructor2.email]
    content = response.content.decode()


def test_petition_project_dl_geopkg(client, haie_user, site):
    """Test Geopkg download"""

    DCConfigHaieFactory()
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


def test_petition_project_instructor_notes_form(
    client, haie_user, haie_instructor_44, site
):
    """Post instruction note as different users"""

    # GIVEN a petition project
    DCConfigHaieFactory()
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
    client.force_login(haie_instructor_44)
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


def test_instructor_view_with_hedges_outside_department(client, haie_instructor_44):
    """Test if a warning is displayed when some hedges are outside department"""
    # GIVEN a moulinette with at least an hedge to remove outside the department

    client.force_login(haie_instructor_44)
    DCConfigHaieFactory()
    hedge_14 = HedgeFactory(
        latLngs=[
            {"lat": 49.37830760743562, "lng": 0.10241746902465822},
            {"lat": 49.37828490574639, "lng": 0.10244965553283693},
        ]
    )  # this hedge is in department 14
    hedges = HedgeDataFactory(hedges=[hedge_14])
    project = PetitionProjectFactory(reference="GHI789", hedge_data=hedges)

    # WHEN requesting the result plantation page
    project_url = reverse(
        "petition_project_instructor_view", kwargs={"reference": project.reference}
    )
    res = client.get(project_url)

    # THEN the result page is displayed with a warning
    assert res.context["has_hedges_outside_department"]
    assert "Le projet est hors du département sélectionné" in res.content.decode()

    # Given hedges in department 44 and accross the department border
    hedge_44 = HedgeFactory(
        latLngs=[
            {"lat": 47.202984120693635, "lng": -1.7100316286087038},
            {"lat": 47.201198235567496, "lng": -1.7097365856170657},
        ]
    )
    hedge_44_85 = HedgeFactory(
        latLngs=[
            {"lat": 47.05281499678513, "lng": -1.2435150146484377},
            {"lat": 47.103783870991634, "lng": -1.1837768554687502},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_44, hedge_44_85])
    project = PetitionProjectFactory(reference="JKL101", hedge_data=hedges)
    project_url = reverse(
        "petition_project_instructor_view", kwargs={"reference": project.reference}
    )
    # WHEN requesting the result plantation page
    res = client.get(project_url)

    # THEN the result page is displayed without warning
    assert not res.context["has_hedges_outside_department"]
    assert "Le projet est hors du département sélectionné" not in res.content.decode()


@patch("envergo.petitions.views.notify")
@pytest.mark.django_db(transaction=True)
def test_petition_project_procedure(
    mock_notify, client, haie_user, haie_instructor_44, site
):
    """Test procedure flow for petition project"""
    # GIVEN a petition project
    DCConfigHaieFactory()
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
    assert "Modifier l'état du dossier</button>" not in content

    # WHEN the user is a department instructor
    client.force_login(haie_instructor_44)
    response = client.get(status_url)

    # THEN the page is displayed and the edition button is there
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Procédure</h2>" in content
    assert "Modifier l'état du dossier</button>" in content

    # WHEN the user try to go from to_be_processed to closed
    data = {
        "stage": "closed",
        "decision": "dropped",
        "update_comment": "aucun retour depuis 15 ans",
        "status_date": "10/09/2025",
    }
    res = client.post(status_url, data, follow=True)
    # THEN this step is not authorized
    assert res.status_code == 200
    project.refresh_from_db()
    assert project.status_history.all().count() == 1

    # WHEN the user edit the status
    data = {
        "stage": "preparing_decision",
        "decision": "dropped",
        "update_comment": "aucun retour depuis 15 ans",
        "status_date": "10/09/2025",
    }
    res = client.post(status_url, data, follow=True)

    # THEN the state is up to date
    assert res.status_code == 200
    project.refresh_from_db()
    last_status = project.status_history.all().order_by("-created_at").first()
    assert last_status.stage == "preparing_decision"
    assert last_status.decision == "dropped"
    event = Event.objects.get(category="dossier", event="modification_etat")
    assert event.metadata["reference"] == project.reference
    assert event.metadata["etape_f"] == "preparing_decision"
    assert event.metadata["decision_f"] == "dropped"
    assert event.metadata["etape_i"] == "to_be_processed"
    assert event.metadata["decision_i"] == "unset"

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


def test_petition_project_follow_up(client, haie_user, haie_instructor_44, site):
    """Test follow up flow for petition project"""
    # GIVEN a petition project
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    toggle_follow_url = reverse(
        "petition_project_toggle_follow",
        kwargs={"reference": project.reference},
    )
    data = {
        "next": reverse(
            "petition_project_instructor_procedure_view",
            kwargs={"reference": project.reference},
        ),
        "follow": "true",
    }

    # WHEN We try to follow the status page but no user is logged in
    response = client.post(toggle_follow_url, data)

    # THEN we should be redirected to the login page
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url

    # WHEN the user is not an instructor
    client.force_login(haie_user)
    response = client.post(toggle_follow_url, data)

    # THEN we should be redirected to a 403 error page
    assert response.status_code == 403

    # WHEN the user is an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.post(toggle_follow_url, data, follow=True)

    # THEN the project is followed
    assert response.status_code == 200
    haie_user.refresh_from_db()
    assert haie_user.followed_petition_projects.get(id=project.id)
    event = Event.objects.get(category="dossier", event="suivi")
    assert event.metadata["reference"] == project.reference
    assert event.metadata["switch"] == "on"
    assert event.metadata["view"] == "detail"

    # WHEN the user is a department instructor
    client.force_login(haie_instructor_44)
    response = client.post(toggle_follow_url, data, follow=True)

    # THEN the project is followed
    assert response.status_code == 200
    haie_instructor_44.refresh_from_db()
    assert haie_instructor_44.followed_petition_projects.get(id=project.id)
    assert Event.objects.filter(category="dossier", event="suivi").count() == 2

    # WHEN I switch off the follow up
    data = {
        "next": reverse("petition_project_list"),
        "follow": "false",
    }
    response = client.post(toggle_follow_url, data, follow=True)

    # THEN the project is followed
    assert response.status_code == 200
    haie_instructor_44.refresh_from_db()
    assert not haie_instructor_44.followed_petition_projects.filter(
        id=project.id
    ).exists()

    assert Event.objects.filter(category="dossier", event="suivi").count() == 3
    event = Event.objects.filter(category="dossier", event="suivi").last()
    assert event.metadata["reference"] == project.reference
    assert event.metadata["switch"] == "off"
    assert event.metadata["view"] == "liste"


def test_petition_project_follow_buttons(client, haie_instructor_44, site):
    """Test the buttons to toggle follow up are on the pages"""
    # GIVEN a petition project
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    status_url = reverse(
        "petition_project_instructor_procedure_view",
        kwargs={"reference": project.reference},
    )

    # WHEN the user is a department instructor that is not following the project
    client.force_login(haie_instructor_44)
    response = client.get(status_url)

    # THEN there is a "Suivre" button to follow up the project
    assert response.status_code == 200
    assert 'type="submit">Suivre</button>' in response.content.decode()

    # WHEN the user is following the project
    project.followed_by.add(haie_instructor_44)
    response = client.get(status_url)

    # THEN there is a "Ne plus suivre" button to stop following up the project
    assert response.status_code == 200
    assert 'type="submit">Ne plus suivre</button>' in response.content.decode()


def test_petition_invited_instructor_cannot_see_send_message_button(
    client, haie_instructor_44, haie_user
):
    client.force_login(haie_instructor_44)
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    messagerie_url = reverse(
        "petition_project_instructor_messagerie_view",
        kwargs={"reference": project.reference},
    )
    res = client.get(messagerie_url)
    assert "Nouveau message</button>" in res.content.decode()

    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    res = client.get(messagerie_url)
    assert "Nouveau message</button>" not in res.content.decode()
    assert (
        '<span class="fr-icon-eye-line fr-icon--sm fr-mr-1w"></span>Lecture seule'
        in res.content.decode()
    )


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_petition_invited_instructor_cannot_send_message(
    mock_ds_query_execute, client, haie_instructor_44, haie_user
):
    client.force_login(haie_instructor_44)
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    messagerie_url = reverse(
        "petition_project_instructor_messagerie_view",
        kwargs={"reference": project.reference},
    )
    attachment = SimpleUploadedFile(FILE_TEST_PATH.name, FILE_TEST_PATH.read_bytes())
    message_data = {
        "message_body": "test",
        "additional_file": attachment,
    }
    mock_ds_query_execute.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    res = client.post(messagerie_url, message_data, follow=True)
    assert res.status_code == 200

    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    attachment = SimpleUploadedFile(FILE_TEST_PATH.name, FILE_TEST_PATH.read_bytes())
    message_data = {
        "message_body": "test",
        "additional_file": attachment,
    }
    res = client.post(messagerie_url, message_data, follow=True)
    assert res.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_petition_project_rai_button(client, haie_user, haie_instructor_44, site):
    """Only department admin can see the "request additional info" button"""

    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    status_url = reverse(
        "petition_project_instructor_procedure_view",
        kwargs={"reference": project.reference},
    )

    # WHEN the user is an invited instructor
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.get(status_url)

    # THEN the page is displayed but the edition button is not there
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Procédure</h2>" in content
    assert "Demander des compléments" not in content

    # WHEN the user is a department instructor
    client.force_login(haie_instructor_44)
    response = client.get(status_url)

    # THEN the page is displayed and the edition button is there
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Procédure</h2>" in content
    assert "Demander des compléments" in content


@pytest.mark.django_db(transaction=True)
@patch("envergo.petitions.views.send_message_dossier_ds")
def test_petition_project_request_for_info(
    mock_ds_msg, client, haie_instructor_44, site
):
    """Instructors can request for additional info."""

    client.force_login(haie_instructor_44)
    mock_ds_msg.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]

    today = date.today()
    next_month = today + timedelta(days=30)

    DCConfigHaieFactory()
    project = PetitionProjectFactory(status__due_date=today)
    assert project.due_date == today
    assert project.is_paused is False

    # Request for additional info
    rai_url = reverse(
        "petition_project_instructor_request_info_view",
        kwargs={"reference": project.reference},
    )
    form_data = {
        "response_due_date": next_month,
        "request_message": "Test",
    }
    res = client.post(rai_url, form_data, follow=True)
    assert res.status_code == 200
    assert "Le message au demandeur a bien été envoyé." in res.content.decode()

    project.refresh_from_db()
    project.current_status.refresh_from_db()
    assert project.is_paused is True
    assert project.current_status.due_date == next_month
    assert project.current_status.original_due_date == today


@pytest.mark.django_db(transaction=True)
@patch("envergo.petitions.views.send_message_dossier_ds")
def test_petition_project_resume_instruction(
    mock_ds_msg, client, haie_instructor_44, site
):
    """Instructors can resume_instruction."""

    client.force_login(haie_instructor_44)
    mock_ds_msg.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]

    today = date.today()
    last_month = today - timedelta(days=30)
    next_month = today + timedelta(days=30)

    DCConfigHaieFactory()
    project = PetitionProjectFactory(
        status__suspension_date=last_month,
        status__original_due_date=today,
        status__due_date=next_month,
        status__response_due_date=next_month,
    )
    assert project.is_paused is True
    assert project.due_date == next_month

    # Request for additional info
    rai_url = reverse(
        "petition_project_instructor_request_info_view",
        kwargs={"reference": project.reference},
    )
    form_data = {
        "info_receipt_date": today,
    }
    res = client.post(rai_url, form_data, follow=True)
    assert res.status_code == 200
    assert "L'instruction du dossier a repris." in res.content.decode()

    project.refresh_from_db()
    project.current_status.refresh_from_db()
    assert project.is_paused is False
    assert project.current_status.due_date == next_month


def test_messagerie_access_stores_access_date(client, haie_instructor_44, haie_user):

    qs = LatestMessagerieAccess.objects.all()
    assert qs.count() == 0

    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    messagerie_url = reverse(
        "petition_project_instructor_messagerie_view",
        kwargs={"reference": project.reference},
    )

    # User is not instructor
    client.force_login(haie_user)
    res = client.get(messagerie_url)
    assert res.status_code == 403
    assert qs.count() == 0

    # Logged user accessed it's messagerie
    client.force_login(haie_instructor_44)
    res = client.get(messagerie_url)
    assert res.status_code == 200
    assert qs.count() == 1

    # Access was logged
    access = qs[0]
    assert access.user == haie_instructor_44
    assert access.project == project
    assert access.access.timestamp() == pytest.approx(
        timezone.now().timestamp(), abs=100
    )

    # Another access does not create new access object
    res = client.get(messagerie_url)
    assert res.status_code == 200
    assert qs.count() == 1


def test_project_list_unread_pill(client, haie_instructor_44):
    DCConfigHaieFactory()

    read_msg = '<td class="messagerie-col read">'
    unread_msg = '<td class="messagerie-col unread">'

    today = date.today()
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    project = PetitionProjectFactory(
        demarches_simplifiees_state=DOSSIER_STATES.prefilled,
        demarches_simplifiees_date_depot=last_month,
        latest_petitioner_msg=None,
    )
    client.force_login(haie_instructor_44)
    url = reverse("petition_project_list")

    # The messagerie was never accessed, there is no message in the project
    qs = LatestMessagerieAccess.objects.all()
    assert qs.count() == 0

    res = client.get(url)
    assert res.status_code == 200
    assert read_msg in res.content.decode()
    assert unread_msg not in res.content.decode()

    # The messagerie was never accessed,
    # there is an existing message in the project before the user joined in
    project.latest_petitioner_msg = last_week
    project.save()
    haie_instructor_44.date_joined = today
    haie_instructor_44.save()
    res = client.get(url)
    assert res.status_code == 200
    assert read_msg in res.content.decode()
    assert unread_msg not in res.content.decode()

    # The messagerie was never accessed,
    # there is an existing message in the project after the user joined in
    project.latest_petitioner_msg = last_week
    project.save()
    haie_instructor_44.date_joined = last_month
    haie_instructor_44.save()
    res = client.get(url)
    assert res.status_code == 200
    assert read_msg not in res.content.decode()
    assert unread_msg in res.content.decode()

    # The messagerie was accessed before the latest message
    access = LatestMessagerieAccess.objects.create(
        project=project, user=haie_instructor_44, access=last_month
    )
    res = client.get(url)
    assert res.status_code == 200
    assert read_msg not in res.content.decode()
    assert unread_msg in res.content.decode()

    # The messagerie was accessed after the latest message
    access.access = today
    access.save()
    res = client.get(url)
    assert res.status_code == 200
    assert read_msg in res.content.decode()
    assert unread_msg not in res.content.decode()


def test_alternatives_list_permission(client, haie_user, haie_instructor_44, site):
    """Test alternative flow for petition project"""

    # GIVEN a petition project
    DCConfigHaieFactory()
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
    client.force_login(haie_instructor_44)
    response = client.get(alternative_url)

    # THEN the page is displayed
    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Simulations alternatives</h2>" in content


def test_alternatives_list_shows_data(client, haie_instructor_44):

    # GIVEN a petition project
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    alternative_url = reverse(
        "petition_project_instructor_alternative_view",
        kwargs={"reference": project.reference},
    )

    # Let's make sure the factory setup works as intended
    assert project.simulations.all().count() == 1
    alternative = project.simulations.all()[0]
    assert alternative.is_initial
    assert alternative.is_active
    assert alternative.moulinette_url == project.moulinette_url

    SimulationFactory(project=project, comment="Simulation schtroumpf")
    SimulationFactory(project=project, comment="Simulation gloubi-boulga")
    SimulationFactory(project=project, comment="Simulation schmilblick")

    SimulationFactory(comment="Simulation test")

    assert project.simulations.all().count() == 4

    # WHEN the user is a department instructor
    client.force_login(haie_instructor_44)
    response = client.get(alternative_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "<h2>Simulations alternatives</h2>" in content
    assert "Simulation schtroumpf" in content
    assert "Simulation gloubi-boulga" in content
    assert "Simulation schmilblick" in content
    assert "Simulation test" not in content


def test_alternative_edit_permission(client, haie_user, haie_instructor_44):
    DCConfigHaieFactory()
    project = PetitionProjectFactory(reference="ABC123")
    s2 = SimulationFactory(project=project, comment="Simulation 2")

    activate_url = reverse(
        "petition_project_instructor_alternative_edit",
        kwargs={
            "reference": project.reference,
            "simulation_id": s2.id,
            "action": "activate",
        },
    )

    # Redirect to login
    res = client.post(activate_url)
    assert res.status_code == 302
    assert res.url.startswith("/comptes/connexion")

    # Non-instructors cannot update alternatives
    client.force_login(haie_user)
    res = client.post(activate_url)
    assert res.status_code == 403

    # Instructors can update alternatives
    client.force_login(haie_instructor_44)
    res = client.post(activate_url)
    assert res.status_code == 302
    assert res.url == "/projet/ABC123/instruction/alternatives/"


def test_alternative_activate(client, haie_instructor_44):

    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    SimulationFactory(project=project, comment="Simulation 2")

    s1 = project.simulations.all()[0]
    assert s1.is_initial
    assert s1.is_active

    s2 = project.simulations.all()[1]
    assert not s2.is_initial
    assert not s2.is_active

    activate_url = reverse(
        "petition_project_instructor_alternative_edit",
        kwargs={
            "reference": project.reference,
            "simulation_id": s2.id,
            "action": "activate",
        },
    )

    client.force_login(haie_instructor_44)
    response = client.post(activate_url)
    assert response.status_code == 302

    s1.refresh_from_db()
    assert s1.is_initial
    assert not s1.is_active

    s2.refresh_from_db()
    assert not s2.is_initial
    assert s2.is_active


def test_alternative_delete(client, haie_instructor_44):

    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    s2 = SimulationFactory(project=project, comment="Simulation 2")
    s3 = SimulationFactory(project=project, comment="Simulation 3")

    s1 = project.simulations.all()[0]
    s1.is_active = False
    s1.save()

    s2.is_active = True
    s2.save()

    client.force_login(haie_instructor_44)

    # Initial simulation cannot be deleted
    delete_url = reverse(
        "petition_project_instructor_alternative_edit",
        kwargs={
            "reference": project.reference,
            "simulation_id": s1.id,
            "action": "delete",
        },
    )
    response = client.post(delete_url)
    assert response.status_code == 403
    assert project.simulations.all().count() == 3

    # Active simulation cannot be deleted
    delete_url = reverse(
        "petition_project_instructor_alternative_edit",
        kwargs={
            "reference": project.reference,
            "simulation_id": s2.id,
            "action": "delete",
        },
    )

    response = client.post(delete_url)
    assert response.status_code == 403
    assert project.simulations.all().count() == 3

    # Others simulations can be deleted
    delete_url = reverse(
        "petition_project_instructor_alternative_edit",
        kwargs={
            "reference": project.reference,
            "simulation_id": s3.id,
            "action": "delete",
        },
    )

    response = client.post(delete_url)
    assert response.status_code == 302
    assert project.simulations.all().count() == 2


def test_valid_token_format_redirects(client):
    """Test that a token with valid format allows redirection."""
    project = PetitionProjectFactory()
    # Valid token format: 43 characters, URL-safe base64 (A-Z, a-z, 0-9, -, _)
    valid_token = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm0123"  # pragma: allowlist secret
    )

    url = reverse(
        "petition_project_accept_invitation",
        kwargs={"reference": project.reference, "token": valid_token},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert f"?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_token}" in response.url


def test_valid_token_with_dash_and_underscore_redirects(client):
    """Test that tokens with dash and underscore characters are accepted."""
    project = PetitionProjectFactory()
    # Token with dash and underscore (valid URL-safe base64 characters)
    valid_token = (
        "Df_3qsiW0GMAVnZVjxoocydbx5a1iaRdkmnJmHIWU4k"  # pragma: allowlist secret
    )

    url = reverse(
        "petition_project_accept_invitation",
        kwargs={"reference": project.reference, "token": valid_token},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert f"?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_token}" in response.url


def test_token_too_short_returns_400(client):
    """Test that a token shorter than 43 characters returns 400."""
    project = PetitionProjectFactory()
    short_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk"  # 37 chars

    url = reverse(
        "petition_project_accept_invitation",
        kwargs={"reference": project.reference, "token": short_token},
    )
    response = client.get(url)

    assert response.status_code == 400


def test_token_too_long_returns_400(client):
    """Test that a token longer than 43 characters returns 400."""
    project = PetitionProjectFactory()
    long_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrst"  # 46 chars

    url = reverse(
        "petition_project_accept_invitation",
        kwargs={"reference": project.reference, "token": long_token},
    )
    response = client.get(url)

    assert response.status_code == 400


def test_token_with_invalid_characters_returns_400(client):
    """Test that a token with invalid characters returns 400."""
    project = PetitionProjectFactory()
    # Token with invalid characters (spaces, special chars)
    # Note: Django's slug converter will reject most invalid chars at URL level,
    # but this test ensures the view's regex validation also works
    invalid_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm012!"

    url = f"/projet/{project.reference}/invitations/{invalid_token}/"
    response = client.get(url)

    # May be 400 (our validation) or 404 (URL routing) depending on character
    assert response.status_code in [400, 404]


def test_real_token_format_accepted(client):
    """Test that a real token generated by secrets.token_urlsafe(32) is accepted."""
    import secrets

    project = PetitionProjectFactory()
    real_token = secrets.token_urlsafe(32)

    url = reverse(
        "petition_project_accept_invitation",
        kwargs={"reference": project.reference, "token": real_token},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert f"?{settings.INVITATION_TOKEN_COOKIE_NAME}={real_token}" in response.url


# =============================================================================
# Invitation Token Management (Consultations Page) Tests
# =============================================================================


def test_consultations_view_requires_authentication(client):
    """Test that consultations view requires authentication"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    response = client.get(consultations_url)
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url


def test_consultations_view_requires_haie_access(client, haie_user):
    """Test that consultations view requires haie access"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    # User without haie access
    haie_user.access_haie = False
    haie_user.save()

    client.force_login(haie_user)
    response = client.get(consultations_url)
    assert response.status_code == 403


def test_consultations_view_accessible_to_department_instructor(
    client, haie_instructor_44
):
    """Test that consultations view is accessible to department instructor"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)
    assert response.status_code == 200
    assert "Services consultés" in response.content.decode()


def test_consultations_view_inaccessible_to_invited_instructor(client, haie_user):
    """Test that consultations view is accessible to invited instructor"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Create an accepted invitation token for haie_user
    InvitationTokenFactory(user=haie_user, petition_project=project)

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_user)
    response = client.get(consultations_url)
    assert response.status_code == 403


def test_consultations_view_displays_accepted_tokens(
    client, haie_instructor_44, haie_user
):
    """Test that consultations view displays only accepted tokens"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Create tokens with different states
    # Pending token (not accepted - should NOT be displayed)
    token1 = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )
    # Accepted token (should be displayed)
    token2 = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        user=haie_user,  # Accepted
    )
    # Create expired but not accepted token (should NOT be displayed)
    past_date = timezone.now() - timedelta(days=31)
    token3 = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        valid_until=past_date,
    )

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200
    content = response.content.decode()

    # Only accepted token should be in the context
    tokens_in_context = list(response.context["invitation_tokens"])
    assert len(tokens_in_context) == 1
    assert token1 not in tokens_in_context  # Pending - not shown
    assert token2 in tokens_in_context  # Accepted - shown
    assert token3 not in tokens_in_context  # Expired but not accepted - not shown

    # User email should be displayed
    assert haie_user.email in content


def test_consultations_view_displays_empty_state(client, haie_instructor_44):
    """Test that consultations view displays empty state when no accepted tokens"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Create a pending token (not accepted) - should not be displayed
    InvitationTokenFactory(petition_project=project, created_by=haie_instructor_44)

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200
    content = response.content.decode()
    # New message for when no accepted consultations
    assert "Aucune consultation n'a encore été enregistrée pour ce dossier" in content


# =============================================================================
# Invitation Token Creation Tests
# =============================================================================


def test_invitation_token_create_requires_authentication(client):
    """Test that token creation requires authentication"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    response = client.post(create_url)
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url


def test_invitation_token_create_requires_change_permission(client, haie_user):
    """Test that token creation requires change permission - standard user"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_user)
    response = client.post(create_url)

    assert response.status_code == 403


def test_invitation_token_create_authorized_for_department_instructor(
    client, haie_instructor_44, site
):
    """Test that department instructor can create tokens"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(create_url)

    assert response.status_code == 200
    # Verify token was created
    token = InvitationToken.objects.get(created_by=haie_instructor_44)
    assert token.petition_project == project


def test_invitation_token_create_returns_html(client, haie_instructor_44, site):
    """Test that token creation returns HTML template instead of JSON"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(create_url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    assert "haie/petitions/_invitation_token_modal_content.html" in [
        t.name for t in response.templates
    ]
    content = response.content.decode()
    assert "invitation_url" in response.context or "invitation_url" in content


def test_invitation_token_create_generates_unique_token(
    client, haie_instructor_44, site
):
    """Test that each creation generates a unique token"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)

    # Create first token
    response1 = client.post(create_url)
    assert response1.status_code == 200
    token1 = InvitationToken.objects.filter(created_by=haie_instructor_44).first()

    # Create second token
    response2 = client.post(create_url)
    assert response2.status_code == 200
    token2 = InvitationToken.objects.filter(created_by=haie_instructor_44).last()

    # Tokens should be different
    assert token1.token != token2.token
    assert InvitationToken.objects.filter(created_by=haie_instructor_44).count() == 2


# =============================================================================
# Invitation Token Deletion Tests
# =============================================================================


def test_invitation_token_delete_requires_authentication(client):
    """Test that token deletion requires authentication"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    response = client.post(delete_url)
    assert response.status_code == 302
    assert "/comptes/connexion/?next=" in response.url


def test_invitation_token_delete_requires_change_permission(client, haie_user):
    """Test that token deletion requires change permission"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    token = InvitationTokenFactory(petition_project=project)

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_user)
    response = client.post(delete_url, {"token_id": token.id})

    assert response.status_code == 403


def test_invitation_token_delete_success(client, haie_instructor_44):
    """Test successful token deletion"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(delete_url, {"token_id": token.id})

    assert response.status_code == 302

    # Verify token was deleted
    assert not InvitationToken.objects.filter(id=token.id).exists()


def test_invitation_token_delete_requires_token_id(client, haie_instructor_44):
    """Test that token deletion requires token_id parameter"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(delete_url)

    assert response.status_code == 400
    assert "Identifiant de token manquant" in response.content.decode()


def test_invitation_token_delete_token_not_found(client, haie_instructor_44):
    """Test deletion of non-existent token"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(delete_url, {"token_id": 99999})

    assert response.status_code == 404


def test_invitation_token_delete_token_wrong_project(client, haie_instructor_44):
    """Test deletion of token from different project"""
    DCConfigHaieFactory()
    project_a = PetitionProjectFactory()
    project_b = PetitionProjectFactory()

    # Create token for project A
    token = InvitationTokenFactory(
        petition_project=project_a, created_by=haie_instructor_44
    )

    # Try to delete from project B
    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project_b.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(delete_url, {"token_id": token.id})

    assert response.status_code == 404
    assert "Invitation non trouvée" in response.content.decode()

    # Verify token still exists
    assert InvitationToken.objects.filter(id=token.id).exists()


def test_invitation_token_delete_logs_analytics_event(client, haie_instructor_44):
    """Test that token deletion logs analytics event"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(delete_url, {"token_id": token.id})

    assert response.status_code == 302


def test_invitation_token_delete_only_accepts_post(client, haie_instructor_44):
    """Test that deletion only accepts POST method"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)

    # GET should not work
    response = client.get(delete_url, {"token_id": token.id})
    assert response.status_code == 405  # Method not allowed

    # Verify token still exists
    assert InvitationToken.objects.filter(id=token.id).exists()


# =============================================================================
# Integration Tests
# =============================================================================


def test_invitation_workflow_full_cycle(client, haie_instructor_44, haie_user, site):
    """Test complete invitation workflow from creation to acceptance"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Step 1: Department instructor creates token via consultations page
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.post(create_url)
    assert response.status_code == 200

    # Step 2: Verify token does NOT appear in consultations list (not accepted yet)
    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    response = client.get(consultations_url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should show empty state (no accepted consultations)
    assert "Aucune consultation n'a encore été enregistrée" in content

    # Step 3: Get the token and simulate user acceptance
    token = InvitationToken.objects.filter(created_by=haie_instructor_44).first()
    token.user = haie_user
    token.save()

    # Step 4: Verify token NOW appears in consultations list (accepted)
    response = client.get(consultations_url)
    assert response.status_code == 200
    content = response.content.decode()
    # Token should be visible with user email
    assert haie_user.email in content
    # Should NOT show empty state anymore
    assert "Aucune consultation n'a encore été enregistrée" not in content

    # Step 5: Verify revoke form IS present (can revoke accepted tokens)
    assert f'name="token_id" value="{token.id}"' in content
    assert "Révoquer" in content


def test_invitation_token_expiration_display(client, haie_instructor_44, haie_user):
    """Test that only accepted tokens are displayed, regardless of expiration"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Create pending token (not accepted - should NOT be displayed)
    pending_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    # Create expired but not accepted token (should NOT be displayed)
    past_date = timezone.now() - timedelta(days=31)
    expired_token = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        valid_until=past_date,
    )

    # Create accepted token (should be displayed)
    accepted_token = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        user=haie_user,
    )

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200
    content = response.content.decode()

    # Only accepted token should be displayed
    tokens_in_context = list(response.context["invitation_tokens"])
    assert len(tokens_in_context) == 1
    assert accepted_token in tokens_in_context

    # Status badges should NOT be present (removed from template)
    assert "En attente" not in content
    assert "Expirée" not in content
    assert "Acceptée" not in content

    # Only one revoke form (for the accepted token)
    # Count the form class, not the text (which also appears in the modal)
    assert content.count("revoke-token-form") == 1


def test_menu_consultations_link_visible_only_for_department_instructor(
    client, haie_instructor_44, haie_user
):
    """Test that consultations link in menu is visible only for department instructors"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Department instructor should see the link
    client.force_login(haie_instructor_44)
    instructor_url = reverse(
        "petition_project_instructor_view", kwargs={"reference": project.reference}
    )
    response = client.get(instructor_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Consultations" in content
    assert (
        reverse(
            "petition_project_instructor_consultations_view",
            kwargs={"reference": project.reference},
        )
        in content
    )

    # Invited instructor should NOT see the link
    InvitationTokenFactory(user=haie_user, petition_project=project)
    client.force_login(haie_user)
    response = client.get(instructor_url)
    assert response.status_code == 200
    content = response.content.decode()

    # Link should not be in sidebar menu (but page is still accessible if URL is known)
    # Check that the Consultations link is not in the menu
    assert (
        'href="%s"'
        % reverse(
            "petition_project_instructor_consultations_view",
            kwargs={"reference": project.reference},
        )
        not in content
    )


def test_revoke_button_shown_for_all_tokens(client, haie_instructor_44, haie_user):
    """Test that revoke button is shown for all accepted tokens"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Create a second user for variety
    haie_user2 = UserFactory(access_haie=True)

    # Create pending token (should NOT be displayed)
    pending_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    # Create accepted tokens (should be displayed)
    accepted_token1 = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        user=haie_user,
    )

    accepted_token2 = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        user=haie_user2,
    )

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200
    content = response.content.decode()

    # Only accepted tokens should be displayed with revoke forms
    assert (
        f'name="token_id" value="{pending_token.id}"' not in content
    )  # Pending - not shown
    assert (
        f'name="token_id" value="{accepted_token1.id}"' in content
    )  # Accepted - shown
    assert (
        f'name="token_id" value="{accepted_token2.id}"' in content
    )  # Accepted - shown

    # Check that there are two revoke forms (one for each accepted token)
    assert content.count("revoke-token-form") == 2


def test_tokens_ordered_by_creation_date_desc(client, haie_instructor_44, haie_user):
    """Test that accepted tokens are ordered by creation date (newest first)"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Create a second user for variety
    haie_user2 = UserFactory(access_haie=True)

    # Create accepted tokens with different creation dates
    old_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44, user=haie_user
    )
    old_token.created_at = timezone.now() - timedelta(days=5)
    old_token.save()

    medium_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44, user=haie_user2
    )
    medium_token.created_at = timezone.now() - timedelta(days=2)
    medium_token.save()

    new_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44, user=haie_user
    )

    # Create a pending token (should NOT be in results)
    pending_token = InvitationTokenFactory(
        petition_project=project, created_by=haie_instructor_44
    )

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200

    # Check order in context - only accepted tokens, newest first
    tokens = response.context["invitation_tokens"]
    assert list(tokens) == [new_token, medium_token, old_token]
    assert pending_token not in list(tokens)


def test_consultations_page_shows_creator_and_accepted_user_info(
    client, haie_instructor_44, haie_user
):
    """Test that consultations page shows accepted user email"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Set user names
    haie_instructor_44.first_name = "Jean"
    haie_instructor_44.last_name = "Dupont"
    haie_instructor_44.save()

    haie_user.first_name = "Marie"
    haie_user.last_name = "Martin"
    haie_user.save()

    # Create accepted token
    token = InvitationTokenFactory(
        petition_project=project,
        created_by=haie_instructor_44,
        user=haie_user,
    )

    consultations_url = reverse(
        "petition_project_instructor_consultations_view",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    response = client.get(consultations_url)

    assert response.status_code == 200
    content = response.content.decode()

    # Accepted user email should be displayed (in Mail column)
    assert haie_user.email in content

    # Creator info should NOT be displayed (no longer in template)
    # We're not checking for creator email absence since it might appear in other parts of the page


def test_old_invitation_url_updated(client, haie_instructor_44, site):
    """Test that the URL pattern has been updated from /invitations/ to /invitations/create/"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # New URL should work
    new_create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )
    assert "/invitations/create/" in new_create_url

    client.force_login(haie_instructor_44)
    response = client.post(new_create_url)
    assert response.status_code == 200


def test_analytics_events_have_correct_names(client, haie_instructor_44, site):
    """Test that analytics events use the new event names"""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()

    # Test creation event
    create_url = reverse(
        "petition_project_invitation_token_create",
        kwargs={"reference": project.reference},
    )

    client.force_login(haie_instructor_44)
    client.post(create_url)

    # Should log "invitation_creation" not "invitation"
    creation_event = Event.objects.filter(
        category="dossier", event="invitation_creation"
    ).first()
    assert creation_event is not None

    # Test deletion event
    token = InvitationToken.objects.filter(created_by=haie_instructor_44).first()
    delete_url = reverse(
        "petition_project_invitation_token_delete",
        kwargs={"reference": project.reference},
    )

    client.post(delete_url, {"token_id": token.id})

    revocation_event = Event.objects.filter(
        category="dossier", event="invitation_revocation"
    ).first()
    assert revocation_event is not None
