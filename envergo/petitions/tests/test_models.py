from datetime import date
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import AnonymousUser

from envergo.analytics.models import Event
from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import Department34Factory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.models import (
    DOSSIER_STATES,
    LOG_TYPES,
    PetitionProject,
    ResultSnapshot,
    StatusLog,
)
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
    SimulationFactory,
)
from envergo.users.tests.factories import UserFactory
from envergo.utils.urls import update_qs

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department.department == "44"


def test_petition_project_view_and_change_permissions(haie_user, admin_user):
    """Per-role matrix for has_view_permission / has_change_permission (referentiel)."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    dept = project.department
    other_dept = Department34Factory()

    # Coordinator on the project's department: can view AND change.
    coordinator = UserFactory(is_haie_coordinator=True)
    coordinator.departments.add(dept)

    # Coordinator on another department: no access at all on this project.
    other_coordinator = UserFactory(is_haie_coordinator=True)
    other_coordinator.departments.add(other_dept)

    # Consulted instructor (department access, not coordinator): view only.
    instructor = UserFactory(is_haie_user=True)
    instructor.departments.add(dept)

    # Invited on the dossier through a token: view only.
    invited = UserFactory(is_haie_user=True)
    InvitationTokenFactory(user=invited, petition_project=project)

    # Superuser: everything.
    assert project.has_view_permission(admin_user)
    assert project.has_change_permission(admin_user)

    assert project.has_view_permission(coordinator)
    assert project.has_change_permission(coordinator)

    assert project.has_view_permission(instructor)
    assert not project.has_change_permission(instructor)

    assert project.has_view_permission(invited)
    assert not project.has_change_permission(invited)

    # Guest (authenticated, no dept/token) and wrong-department coordinator: nothing.
    assert not project.has_view_permission(haie_user)
    assert not project.has_change_permission(haie_user)
    assert not project.has_view_permission(other_coordinator)
    assert not project.has_change_permission(other_coordinator)


def test_petition_project_permissions_for_anonymous_user():
    """An anonymous user has neither view nor change permission.

    AnonymousUser is not a User: it carries none of the guichet fields, so the
    permission checks must rule it out before reading them.
    """
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    anonymous = AnonymousUser()

    assert not project.has_view_permission(anonymous)
    assert not project.has_change_permission(anonymous)


def test_form_url_adds_alternative_param():
    """form_url appends project_reference to the query string."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project)

    # Check that "project_reference" is not already in the initial url
    url = simulation.moulinette_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "project_reference" not in params

    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["project_reference"] == [project.reference]


def test_form_url_does_not_duplicate_alternative_param():
    """form_url replaces an existing project_reference param instead of appending a second one."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Create a simulation whose moulinette_url already contains project_reference
    moulinette_url = project.moulinette_url + "&project_reference=" + project.reference
    simulation = SimulationFactory(project=project, moulinette_url=moulinette_url)
    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Should have exactly one value, not two
    assert params["project_reference"] == [project.reference]


@pytest.mark.haie
def test_result_url_adds_alternative_param():
    """result_url appends project_reference for new simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project, is_active=False)
    url = simulation.result_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["project_reference"] == [project.reference]


@pytest.mark.haie
def test_result_url_active_returns_project_url():
    """result_url points to the project page (without project_reference param) for active simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Deactivate the initial simulation created by the factory
    project.simulations.update(is_active=False)
    simulation = SimulationFactory(project=project, is_active=True)
    url = simulation.result_url
    assert f"/projet/{project.reference}/" in url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "project_reference" not in params


def test_pinned_simulation_date_replaces_the_evaluated_date():
    """Pinning the simulation date changes the date the project is evaluated on."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    assert project.date != date(2025, 1, 29)

    project.pin_simulation_date(date(2025, 1, 29))

    assert project.date == date(2025, 1, 29)


def test_reloaded_project_is_evaluated_on_its_stored_date():
    """A reload picks up the simulation date stored in the database."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    assert project.date != date(2025, 1, 29)
    pinned_url = update_qs(project.moulinette_url, {"date": "2025-01-29"})
    PetitionProject.objects.filter(pk=project.pk).update(moulinette_url=pinned_url)

    project.refresh_from_db()

    assert project.date == date(2025, 1, 29)


def fake_dossier(state):
    """A « Démarche numérique » dossier, as the synchronization reads it."""
    return {
        "id": "RG9zc2llci0yMzE3ODQ0Mw==",
        "state": state,
        "dateDepot": "2025-01-29T16:25:03+01:00",
        "usager": {"email": "test@example.com"},
        "demarche": {"number": 103363},
    }


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

    @pytest.mark.haie
    def test_snapshot_created_on_dossier_submission(self):
        """A ResultSnapshot is created when a dossier is submitted via synchronize_with_demarches_simplifiees."""
        SiteFactory(domain="testserver", name="testserver")

        DCConfigHaieFactory()
        # Create project in draft state (not yet submitted)
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)

        # Count snapshots after project creation
        initial_count = ResultSnapshot.objects.filter(project=project).count()

        # Simulate dossier submission from « Démarche numérique »
        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

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


# The sync's commit callbacks only run in a real transaction.
@pytest.mark.django_db(transaction=True)
class TestDemarcheNumeriqueSync:
    """Synchronization of a project with its « Démarche numérique » dossier."""

    @pytest.mark.haie
    def test_simulations_date_updated_on_dossier_submission(self):
        """All simulations get the date param added to their moulinette_url on first submission."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)
        alternative = SimulationFactory(project=project, comment="Alternative")

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        alternative.refresh_from_db()
        assert "date=2025-01-29" in alternative.moulinette_url

    @pytest.mark.haie
    def test_auto_instruction_ru_sets_instruction_d_with_due_date(self):
        """A « ru » dossier arriving en_instruction is auto-moved to instruction_d
        with a due date equal to the deposit date."""
        from django.contrib.sites.models import Site

        Site.objects.get_or_create(domain="testserver", defaults={"name": "testserver"})

        DCConfigHaieFactory()
        # Default factory category is "ru"
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)
        assert project.stage == "to_be_processed"

        project.synchronize_with_demarche_numerique(fake_dossier("en_instruction"))

        status_log = StatusLog.objects.filter(
            petition_project=project,
            type=LOG_TYPES.status_change,
            stage="instruction_d",
        ).first()
        assert status_log is not None
        # Due date is the deposit date + 2 months (instruction period)
        assert status_log.due_date == date(2025, 3, 29)

        project.refresh_from_db()
        assert project.stage == "instruction_d"
        assert project.due_date == date(2025, 3, 29)

    @pytest.mark.haie
    def test_auto_instruction_non_ru_sets_instruction_h_without_due_date(self):
        """A non-« ru » dossier arriving en_instruction is auto-moved to instruction_h
        without a due date."""
        from django.contrib.sites.models import Site

        Site.objects.get_or_create(domain="testserver", defaults={"name": "testserver"})

        DCConfigHaieFactory()
        project = PetitionProjectFactory(
            underscore_category="hru",
            demarche_numerique_state=DOSSIER_STATES.draft,
        )
        assert project.stage == "to_be_processed"

        project.synchronize_with_demarche_numerique(fake_dossier("en_instruction"))

        status_log = StatusLog.objects.filter(
            petition_project=project,
            type=LOG_TYPES.status_change,
            stage="instruction_h",
        ).first()
        assert status_log is not None
        assert status_log.due_date is None

        project.refresh_from_db()
        assert project.stage == "instruction_h"
        assert project.due_date is None

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    def test_ru_dossier_submission_sends_the_declaration_receipt(self, mock_task):
        """A « ru » dossier opens the two month tacit agreement delay on deposit."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        # Default factory category is "ru"
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)

        project.synchronize_with_demarche_numerique(fake_dossier("en_instruction"))

        assert mock_task.delay.call_count == 1
        # Due two months after the dépôt
        assert mock_task.delay.call_args[0] == (
            project.pk,
            "2025-01-29",
            "2025-03-29",
        )

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    def test_non_ru_dossier_submission_sends_no_receipt(self, mock_task):
        """Outside the régime unique, no tacit agreement delay, hence no receipt."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(
            underscore_category="hru",
            demarche_numerique_state=DOSSIER_STATES.draft,
        )

        project.synchronize_with_demarche_numerique(fake_dossier("en_instruction"))

        assert not mock_task.delay.called

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    def test_dossier_submission_sends_the_new_dossier_email(self, mock_task):
        """The GUH mailbox hears about a dossier when it is first submitted."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        mock_task.delay.assert_called_once_with(project.pk)

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    def test_resync_of_submitted_dossier_sends_no_new_dossier_email(self, mock_task):
        """A dossier already submitted is not announced again."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(
            demarche_numerique_state=DOSSIER_STATES.en_construction
        )

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        assert not mock_task.delay.called

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.notify")
    def test_state_changed_outside_guh_alerts_the_team(self, mock_notify):
        """A state changed directly on « Démarche numérique » alerts the team."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(
            demarche_numerique_state=DOSSIER_STATES.en_construction
        )

        project.synchronize_with_demarche_numerique(fake_dossier("en_instruction"))

        mock_notify.assert_called_once()
        message = mock_notify.call_args[0][0]
        assert "changement de statut a eu lieu depuis" in message
        project.refresh_from_db()
        assert project.demarche_numerique_state == DOSSIER_STATES.en_instruction

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    @patch("envergo.petitions.tasks.notify")
    def test_resync_with_unchanged_state_has_no_effect(
        self, mock_notify, mock_email_task, mock_receipt_task
    ):
        """A sync that brings no state change alerts nobody and queues nothing."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(
            demarche_numerique_state=DOSSIER_STATES.en_construction
        )
        status_logs = StatusLog.objects.filter(petition_project=project)
        status_log_count = status_logs.count()

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        assert not mock_notify.called
        assert not mock_email_task.delay.called
        assert not mock_receipt_task.delay.called
        assert status_logs.count() == status_log_count

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    @patch("envergo.petitions.tasks.send_team_alert_async")
    @patch(
        "envergo.petitions.models.PetitionProject.update_demarche_numerique_cache",
        side_effect=RuntimeError,
    )
    def test_failed_sync_rolls_back_and_sends_nothing(
        self, mock_cache_update, mock_alert_task, mock_email_task, mock_receipt_task
    ):
        """A sync failing after the dépôt steps leaves the project as it was and sends nothing."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)

        with pytest.raises(RuntimeError):
            project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        project.refresh_from_db()
        assert project.demarche_numerique_state == DOSSIER_STATES.draft
        assert "date=" not in project.moulinette_url
        assert not Event.objects.filter(category="demande", event="depot").exists()
        assert not mock_alert_task.delay.called
        assert not mock_email_task.delay.called
        assert not mock_receipt_task.delay.called

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    @patch("envergo.petitions.tasks.send_team_alert_async")
    def test_stale_copy_does_not_replay_the_submission(
        self, mock_alert_task, mock_email_task, mock_receipt_task
    ):
        """Two syncs of the same draft project handle its dépôt only once."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)
        first_copy = PetitionProject.objects.get(pk=project.pk)
        stale_copy = PetitionProject.objects.get(pk=project.pk)
        dossier = fake_dossier("en_construction")

        first_copy.synchronize_with_demarche_numerique(dossier)
        stale_copy.synchronize_with_demarche_numerique(dossier)

        assert mock_alert_task.delay.call_count == 1
        assert mock_email_task.delay.call_count == 1
        assert mock_receipt_task.delay.call_count == 1

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    @patch("envergo.petitions.tasks.send_team_alert_async")
    def test_failing_alert_enqueue_still_queues_the_other_messages(
        self, mock_alert_task, mock_email_task, mock_receipt_task
    ):
        """A team alert that cannot be queued does not cost the email and receipt."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)
        mock_alert_task.delay.side_effect = ConnectionError

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        assert mock_email_task.delay.call_count == 1
        assert mock_receipt_task.delay.call_count == 1

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_declaration_receipt_async")
    @patch("envergo.petitions.tasks.send_new_dossier_email_async")
    @patch("envergo.petitions.tasks.send_team_alert_async")
    def test_submission_evaluates_the_project_on_its_depot_date(self, *mock_tasks):
        """After the dépôt, the project is evaluated with the rules of its dépôt date."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        project = PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.draft)
        # Evaluated before the sync, as an instructor page does.
        assert project.date != date(2025, 1, 29)
        assert project.get_moulinette().date != date(2025, 1, 29)

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        assert project.date == date(2025, 1, 29)
        assert project.get_moulinette().date == date(2025, 1, 29)

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_team_alert_async")
    def test_older_fetched_copy_is_skipped(self, mock_alert_task):
        """A copy fetched before the dossier's latest change does not overwrite it."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        cached_dossier = fake_dossier("en_instruction")
        cached_dossier["dateDerniereModification"] = "2025-02-01T10:00:00+01:00"
        project = PetitionProjectFactory(
            demarche_numerique_state=DOSSIER_STATES.en_instruction,
            demarche_numerique_raw_dossier=cached_dossier,
        )
        older_copy = fake_dossier("en_construction")
        older_copy["dateDerniereModification"] = "2025-01-31T10:00:00+01:00"

        project.synchronize_with_demarche_numerique(older_copy)

        project.refresh_from_db()
        assert project.demarche_numerique_state == DOSSIER_STATES.en_instruction
        assert not mock_alert_task.delay.called

    @pytest.mark.haie
    @patch("envergo.petitions.tasks.send_team_alert_async")
    def test_fetched_copy_without_modification_date_is_synced(self, mock_alert_task):
        """A copy carrying no modification date is synced as usual."""
        SiteFactory(domain="testserver", name="testserver")
        DCConfigHaieFactory()
        cached_dossier = fake_dossier("en_instruction")
        cached_dossier["dateDerniereModification"] = "2025-02-01T10:00:00+01:00"
        project = PetitionProjectFactory(
            demarche_numerique_state=DOSSIER_STATES.en_instruction,
            demarche_numerique_raw_dossier=cached_dossier,
        )

        project.synchronize_with_demarche_numerique(fake_dossier("en_construction"))

        project.refresh_from_db()
        assert project.demarche_numerique_state == DOSSIER_STATES.en_construction
        assert mock_alert_task.delay.call_count == 1
