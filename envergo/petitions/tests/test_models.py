from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import override_settings

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.models import DOSSIER_STATES, ResultSnapshot
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    PetitionProjectFactory,
    SimulationFactory,
)

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department.department == "44"


def test_form_url_adds_alternative_param():
    """form_url appends alternative=true to the query string."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project)

    # Check that "alternative" is not already in the initial url
    url = simulation.moulinette_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "alternative" not in params

    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["alternative"] == ["true"]


def test_form_url_does_not_duplicate_alternative_param():
    """form_url replaces an existing alternative param instead of appending a second one."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Create a simulation whose moulinette_url already contains alternative=true
    moulinette_url = project.moulinette_url + "&alternative=true"
    simulation = SimulationFactory(project=project, moulinette_url=moulinette_url)
    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Should have exactly one value, not two
    assert params["alternative"] == ["true"]


@pytest.mark.haie
def test_result_url_adds_alternative_param():
    """result_url appends alternative=true for new simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project, is_active=False)
    url = simulation.result_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["alternative"] == ["true"]


@pytest.mark.haie
def test_result_url_active_returns_project_url():
    """result_url points to the project page (without alternative param) for active simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Deactivate the initial simulation created by the factory
    project.simulations.update(is_active=False)
    simulation = SimulationFactory(project=project, is_active=True)
    url = simulation.result_url
    assert f"/projet/{project.reference}/" in url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "alternative" not in params


@pytest.mark.django_db(transaction=True)
class TestResultSnapshot:
    """Tests for ResultSnapshot model and automatic creation."""

    def test_create_for_project(self):
        """ResultSnapshot.create_for_project creates a snapshot with correct data."""
        DCConfigHaieFactory()
        project = PetitionProjectFactory()

        # Clear any snapshots created during project creation
        ResultSnapshot.objects.filter(project=project).delete()

        snapshot = ResultSnapshot.create_for_project(project=project)

        assert snapshot.project == project
        assert snapshot.moulinette_url == project.moulinette_url
        assert "haies" in snapshot.payload
        # The haies field should be the id (UUID) of the hedge_data
        assert snapshot.payload["haies"] == project.hedge_data.id

    def test_snapshot_created_on_new_project(self):
        """A ResultSnapshot is created when a new PetitionProject is saved."""
        DCConfigHaieFactory()

        # Count existing snapshots
        initial_count = ResultSnapshot.objects.count()

        project = PetitionProjectFactory()

        # A snapshot should have been created
        assert ResultSnapshot.objects.count() == initial_count + 1
        snapshot = ResultSnapshot.objects.filter(project=project).first()
        assert snapshot is not None
        assert snapshot.moulinette_url == project.moulinette_url

    def test_snapshot_created_on_moulinette_url_change(self):
        """A ResultSnapshot is created when moulinette_url changes."""
        DCConfigHaieFactory()
        project = PetitionProjectFactory()

        # Count snapshots after project creation
        initial_count = ResultSnapshot.objects.filter(project=project).count()

        # Change the moulinette_url
        new_url = project.moulinette_url.replace("motif=autre", "motif=chemin")
        project.moulinette_url = new_url
        project.save()

        # A new snapshot should have been created
        assert (
            ResultSnapshot.objects.filter(project=project).count() == initial_count + 1
        )
        latest_snapshot = (
            ResultSnapshot.objects.filter(project=project)
            .order_by("-created_at")
            .first()
        )
        assert latest_snapshot.moulinette_url == new_url

    def test_no_snapshot_on_unrelated_field_change(self):
        """No ResultSnapshot is created when unrelated fields change."""
        DCConfigHaieFactory()
        project = PetitionProjectFactory()

        # Count snapshots after project creation
        initial_count = ResultSnapshot.objects.filter(project=project).count()

        # Change an unrelated field
        project.reference = "NEW_REF_123"
        project.save()

        # No new snapshot should have been created
        assert ResultSnapshot.objects.filter(project=project).count() == initial_count

    def test_snapshot_payload_contains_moulinette_summary(self):
        """The snapshot payload contains data from moulinette.summary()."""
        DCConfigHaieFactory()
        project = PetitionProjectFactory()

        snapshot = ResultSnapshot.objects.filter(project=project).first()
        assert snapshot is not None

        # Check that some expected fields from moulinette.summary() are present
        # The exact fields depend on the moulinette configuration
        assert isinstance(snapshot.payload, dict)
        assert "haies" in snapshot.payload

    @pytest.mark.urls("config.urls_haie")
    @override_settings(ENVERGO_HAIE_DOMAIN="testserver")
    @override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
    @patch("envergo.petitions.models.notify")
    @patch("envergo.petitions.models.log_event_raw")
    def test_snapshot_created_on_dossier_submission(self, mock_log_event, mock_notify):
        """A ResultSnapshot is created when a dossier is submitted via synchronize_with_demarches_simplifiees."""
        from django.contrib.sites.models import Site

        Site.objects.get_or_create(domain="testserver", defaults={"name": "testserver"})

        DCConfigHaieFactory()
        # Create project in draft state (not yet submitted)
        project = PetitionProjectFactory(
            demarches_simplifiees_state=DOSSIER_STATES.draft
        )

        # Count snapshots after project creation
        initial_count = ResultSnapshot.objects.filter(project=project).count()

        # Simulate dossier submission from demarches-simplifiees
        fake_dossier = {
            "id": "RG9zc2llci0yMzE3ODQ0Mw==",
            "state": "en_construction",
            "dateDepot": "2025-01-29T16:25:03+01:00",
            "usager": {"email": "test@example.com"},
            "demarche": {"number": 103363},
        }

        project.synchronize_with_demarches_simplifiees(fake_dossier)

        # A new snapshot should have been created because the moulinette_url is updated (adds date param)
        assert (
            ResultSnapshot.objects.filter(project=project).count() == initial_count + 1
        )
        latest_snapshot = (
            ResultSnapshot.objects.filter(project=project)
            .order_by("-created_at")
            .first()
        )
        # The snapshot should have the updated moulinette_url (with date param added)
        assert "date=2025-01-29" in latest_snapshot.moulinette_url
