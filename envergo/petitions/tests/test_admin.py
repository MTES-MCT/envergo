from unittest.mock import Mock, patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.admin import PetitionProjectAdmin
from envergo.petitions.demarche_numerique.client import DemarcheNumeriqueError
from envergo.petitions.models import PetitionProject
from envergo.petitions.tests.factories import (
    DEMARCHE_NUMERIQUE_FAKE,
    GET_DOSSIER_FAKE_RESPONSE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def project_admin():
    return PetitionProjectAdmin(PetitionProject, AdminSite())


@pytest.fixture
def admin_request():
    request = RequestFactory().post("/")
    request.session = "session"
    request._messages = FallbackStorage(request)
    return request


@patch("envergo.petitions.admin.get_demarche_numerique_dossier")
def test_save_model_forces_sync_when_dossier_number_changes(
    mock_get_dossier, project_admin, admin_request
):
    """Manually attaching a dossier number triggers a forced sync."""
    project = PetitionProjectFactory()
    form = Mock(changed_data=["demarche_numerique_dossier_number"])

    project_admin.save_model(admin_request, project, form, change=True)

    mock_get_dossier.assert_called_once_with(project, force_update=True)
    stored = list(get_messages(admin_request))
    assert len(stored) == 1
    assert stored[0].level == messages.SUCCESS


@patch("envergo.petitions.admin.get_demarche_numerique_dossier")
def test_save_model_no_sync_when_dossier_number_unchanged(
    mock_get_dossier, project_admin, admin_request
):
    project = PetitionProjectFactory()
    form = Mock(changed_data=["reference"])

    project_admin.save_model(admin_request, project, form, change=True)

    mock_get_dossier.assert_not_called()
    assert len(list(get_messages(admin_request))) == 0


@patch("envergo.petitions.admin.get_demarche_numerique_dossier")
def test_save_model_no_sync_when_dossier_number_cleared(
    mock_get_dossier, project_admin, admin_request
):
    project = PetitionProjectFactory(demarche_numerique_dossier_number=None)
    form = Mock(changed_data=["demarche_numerique_dossier_number"])

    project_admin.save_model(admin_request, project, form, change=True)

    mock_get_dossier.assert_not_called()


@patch("envergo.petitions.admin.get_demarche_numerique_dossier")
def test_save_model_warns_when_dossier_not_found(
    mock_get_dossier, project_admin, admin_request
):
    mock_get_dossier.return_value = None
    project = PetitionProjectFactory()
    form = Mock(changed_data=["demarche_numerique_dossier_number"])

    project_admin.save_model(admin_request, project, form, change=True)

    stored = list(get_messages(admin_request))
    assert len(stored) == 1
    assert stored[0].level == messages.WARNING


@patch("envergo.petitions.admin.get_demarche_numerique_dossier")
def test_save_model_survives_sync_failure(
    mock_get_dossier, project_admin, admin_request
):
    """A DN API error must not prevent saving the project."""
    mock_get_dossier.side_effect = DemarcheNumeriqueError(message="DN API is down")
    project = PetitionProjectFactory()
    form = Mock(changed_data=["demarche_numerique_dossier_number"])

    project_admin.save_model(admin_request, project, form, change=True)

    assert PetitionProject.objects.filter(pk=project.pk).exists()
    stored = list(get_messages(admin_request))
    assert len(stored) == 1
    assert stored[0].level == messages.ERROR


@pytest.mark.haie
@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.models.notify")
@patch("envergo.petitions.demarche_numerique.client.DemarcheNumeriqueClient.execute")
def test_save_model_synchronizes_project_with_dn(
    mock_post, mock_notify, project_admin, admin_request, site
):
    """End-to-end: saving with a new dossier number populates the DN fields."""
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    assert project.demarche_numerique_last_sync is None
    form = Mock(changed_data=["demarche_numerique_dossier_number"])

    project_admin.save_model(admin_request, project, form, change=True)

    project.refresh_from_db()
    assert project.demarche_numerique_last_sync is not None
    assert project.demarche_numerique_raw_dossier is not None
    mock_post.assert_called_once()
