import datetime
from datetime import date, timedelta
from unittest.mock import call, patch

import pytest
from django.core.management import call_command
from django.db.backends.postgresql.psycopg_any import DateRange
from django.test import override_settings
from django.utils import timezone

from envergo.geodata.tests.factories import Department34Factory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.demarche_numerique.client import DemarcheNumeriqueError
from envergo.petitions.demarche_numerique.models import DossierState
from envergo.petitions.models import PetitionProject
from envergo.petitions.tests.factories import (
    DEMARCHE_NUMERIQUE_FAKE,
    DEMARCHE_NUMERIQUE_FAKE_DISABLED,
    DeclarationProjectFactory,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE_DISABLED)
def test_dossier_submission_admin_alert_ds_not_enabled(caplog):
    PetitionProjectFactory()
    DCConfigHaieFactory()
    call_command("dossier_submission_admin_alert")
    assert (
        len(
            [
                rec.message
                for rec in caplog.records
                if "« Démarche numérique » is not enabled" in rec.message
            ]
        )
        > 0
    )


@pytest.mark.haie
@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_declaration_receipt_async")
@patch("envergo.petitions.tasks.send_new_dossier_email_async")
@patch("envergo.petitions.tasks.notify")
@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch("envergo.petitions.demarche_numerique.client.DemarcheNumeriqueClient.execute")
def test_dossier_submission_admin_alert(
    mock_post,
    mock_notify_command,
    mock_notify_team,
    mock_email_task,
    mock_receipt_task,
    django_capture_on_commit_callbacks,
):
    # Define the first mock response
    mock_response_1 = {
        "demarche": {
            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
            "number": 103363,
            "dossiers": {
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "MjAyNC0xMS0xOVQxMDoyMzowMy45NTc0NDAwMDBaOzIxMDU5Njc1",
                },
                "nodes": [
                    {
                        "number": 21059675,
                        "id": "RG9zc2llci0yMzE3ODQ0Mw==",
                        "state": "en_construction",
                        "dateDepot": "2025-01-29T16:25:03+01:00",
                        "demarche": {
                            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                            "number": 103363,
                        },
                    },
                    {
                        "number": 123,
                        "id": "UW9zc2llci0yRiO3ODQ0Mw==",
                        "state": "en_construction",
                        "dateDepot": "2025-01-29T16:25:03+01:00",
                        "champs": [
                            {
                                "id": "ABC123",
                                "label": "Url du simulateur",
                                "stringValue": "",
                            },
                        ],
                        "demarche": {
                            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                            "number": 103363,
                        },
                    },
                ],
            },
        }
    }

    # Define the second mock response
    mock_response_2 = {
        "demarche": {
            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
            "number": 103363,
            "dossiers": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "number": 21059676,
                        "id": "SH9zc2llci0yMzE3OATrSw==",
                        "state": "en_construction",
                        "dateDepot": "2025-01-29T16:25:03+01:00",
                        "demarche": {
                            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                            "number": 103363,
                        },
                    },
                ],
            },
        }
    }

    mock_post.side_effect = [mock_response_1, mock_response_2]
    project = PetitionProjectFactory()
    assert "date=" not in project.moulinette_url
    DCConfigHaieFactory()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("dossier_submission_admin_alert")

    args, kwargs = mock_notify_team.call_args_list[0]
    assert "### Nouveau dossier – Loire-Atlantique (44)" in args[0]
    assert "haie" in args[1]

    args, kwargs = mock_notify_command.call_args_list[0]
    assert (
        "Un dossier a été déposé sur « Démarche numérique », qui ne correspond à aucun projet dans la base du GUH."
        in args[0]
    )
    assert "(test) Guichet unique de la haie / Demande d'autorisation" in args[0]
    assert "haie" in args[1]

    assert mock_notify_command.call_count == 2
    assert mock_notify_team.call_count == 1
    project.refresh_from_db()
    assert project.demarche_numerique_date_depot == datetime.datetime(
        2025, 1, 29, 15, 25, 3, tzinfo=datetime.timezone.utc
    )
    assert project.demarche_numerique_last_sync is not None
    assert mock_post.call_count == 2
    assert "date=2025-01-29" in project.moulinette_url


@pytest.mark.haie
@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.notify")
@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch("envergo.petitions.demarche_numerique.client.DemarcheNumeriqueClient.execute")
def test_dossier_submission_admin_alert_processes_expired_config(
    mock_post, mock_notify_command, mock_notify_team
):
    """The command should also process expired configs."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    mock_post.return_value = {
        "demarche": {
            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
            "number": 103363,
            "dossiers": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "number": 21059675,
                        "id": "RG9zc2llci0yMzE3ODQ0Mw==",
                        "state": "en_instruction",
                        "dateDepot": "2025-01-29T16:25:03+01:00",
                        "demarche": {
                            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                            "number": 103363,
                        },
                    },
                ],
            },
        }
    }

    # Expired config — dossiers submitted under it must still be synchronized
    DCConfigHaieFactory(
        validity_range=DateRange(one_year_ago, today, "[)"),
    )

    project = PetitionProjectFactory()
    call_command("dossier_submission_admin_alert")

    mock_post.assert_called_once()
    project.refresh_from_db()
    assert project.demarche_numerique_state == DossierState.en_instruction.value
    assert project.demarche_numerique_last_sync is not None


@pytest.mark.haie
@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.notify")
@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch("envergo.petitions.demarche_numerique.client.DemarcheNumeriqueClient.execute")
def test_dossier_submission_admin_alert_stage_instruction(
    mock_post, mock_notify_command, mock_notify_team
):
    """Test if project is with stage instruction on creation when DS returns 'En instruction'"""
    # Define the mock response
    mock_response_1 = {
        "demarche": {
            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
            "number": 103363,
            "dossiers": {
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "MjAyNC0xMS0xOVQxMDoyMzowMy45NTc0NDAwMDBaOzIxMDU5Njc1",
                },
                "nodes": [
                    {
                        "number": 21059675,
                        "id": "RG9zc2llci0yMzE3ODQ0Mw==",
                        "state": "en_instruction",
                        "dateDepot": "2025-01-29T16:25:03+01:00",
                        "demarche": {
                            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                            "number": 103363,
                        },
                    },
                ],
            },
        }
    }
    mock_post.side_effect = [mock_response_1]
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    call_command("dossier_submission_admin_alert")

    project.refresh_from_db()
    assert project.demarche_numerique_state == DossierState.en_instruction.value
    assert project.stage == "instruction_d"
    assert project.due_date == datetime.date(
        2025, 3, 29
    )  # date_depot 2025-01-29 + 2 months


COMMAND_PATH = "envergo.petitions.management.commands.dossier_submission_admin_alert"


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch(f"{COMMAND_PATH}.Command.handle_dossier", side_effect=[RuntimeError, None])
@patch("envergo.petitions.demarche_numerique.client.DemarcheNumeriqueClient.execute")
def test_dossier_submission_admin_alert_survives_a_failing_dossier(
    mock_post, mock_handle_dossier
):
    """A dossier that fails to sync does not stop the next one."""
    mock_post.return_value = {
        "demarche": {
            "title": "(test) Guichet unique de la haie / Demande d'autorisation",
            "number": 103363,
            "dossiers": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "number": 21059675,
                        "id": "RG9zc2llci0x",
                        "state": "en_construction",
                    },
                    {
                        "number": 21059676,
                        "id": "RG9zc2llci0y",
                        "state": "en_construction",
                    },
                ],
            },
        }
    }
    DCConfigHaieFactory()

    call_command("dossier_submission_admin_alert")

    assert mock_handle_dossier.call_count == 2


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch(
    f"{COMMAND_PATH}.Command.synchronize_demarche",
    side_effect=[DemarcheNumeriqueError("", {}, "unreachable"), None],
)
def test_dossier_submission_admin_alert_survives_a_failing_demarche(
    mock_synchronize_demarche,
):
    """A démarche that fails to sync does not stop the next one."""
    DCConfigHaieFactory()
    DCConfigHaieFactory(department=Department34Factory())

    call_command("dossier_submission_admin_alert")

    assert mock_synchronize_demarche.call_count == 2


@pytest.mark.haie
@patch.object(PetitionProject, "close_by_tacit_agreement", autospec=True)
class TestCloseTacitAgreements:
    """The nightly command closing the dossiers whose silence became agreement."""

    @override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
    def test_command_closes_the_due_dossiers_only(self, mock_close):
        """Dossiers due today or earlier are closed. Later ones are left alone."""
        today = timezone.localdate()
        last_week = today - timedelta(days=7)
        tomorrow = today + timedelta(days=1)
        due = DeclarationProjectFactory(agreement_deadline=today)
        overdue = DeclarationProjectFactory(agreement_deadline=last_week)
        DeclarationProjectFactory(agreement_deadline=tomorrow)

        call_command("close_tacit_agreements")

        assert mock_close.call_count == 2
        mock_close.assert_has_calls([call(due), call(overdue)], any_order=True)

    @override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
    def test_one_failed_closing_does_not_stop_the_others(self, mock_close, caplog):
        """The failure is logged. The next dossier is still closed."""
        yesterday = timezone.localdate() - timedelta(days=1)
        failing = DeclarationProjectFactory(agreement_deadline=yesterday)
        other = DeclarationProjectFactory(agreement_deadline=yesterday)

        def close(project):
            """Let « Démarche numérique » reject the failing dossier only."""
            if project == failing:
                raise DemarcheNumeriqueError(message="rejected")

        mock_close.side_effect = close

        call_command("close_tacit_agreements")

        mock_close.assert_has_calls([call(failing), call(other)], any_order=True)
        assert f"closing failed for dossier {failing.reference}" in caplog.text
        assert "1 dossiers closed, 1 failed" in caplog.text

    @override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
    def test_dry_run_lists_the_due_dossiers_without_closing_them(
        self, mock_close, caplog
    ):
        """A dry run shows the dossiers the real run would close."""
        yesterday = timezone.localdate() - timedelta(days=1)
        due = DeclarationProjectFactory(declaration__agreement_deadline=yesterday)

        call_command("close_tacit_agreements", "--dry-run")

        assert not mock_close.called
        assert f"dossier {due.reference} is due since {yesterday}" in caplog.text
        assert "1 dossiers would be closed" in caplog.text

    @override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE_DISABLED)
    def test_command_does_nothing_without_demarche_numerique(self, mock_close):
        """« Démarche numérique » must accept every closing. Without it, each one fails."""
        yesterday = timezone.localdate() - timedelta(days=1)
        DeclarationProjectFactory(agreement_deadline=yesterday)

        call_command("close_tacit_agreements")

        assert not mock_close.called
