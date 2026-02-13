import datetime
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db.backends.postgresql.psycopg_any import DateRange
from django.test import override_settings

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
def test_dossier_submission_admin_alert_ds_not_enabled(caplog):
    PetitionProjectFactory()
    DCConfigHaieFactory()
    call_command("dossier_submission_admin_alert")
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


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.models.notify")
@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_dossier_submission_admin_alert(
    mock_post, mock_notify_command, mock_notify_model
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
    call_command("dossier_submission_admin_alert")

    args, kwargs = mock_notify_model.call_args_list[0]
    assert "### Nouveau dossier – Loire-Atlantique (44)" in args[0]
    assert "haie" in args[1]

    args, kwargs = mock_notify_command.call_args_list[0]
    assert (
        "Un dossier a été déposé sur démarches-simplifiées, qui ne correspond à aucun projet dans la base du GUH."
        in args[0]
    )
    assert "(test) Guichet unique de la haie / Demande d'autorisation" in args[0]
    assert "haie" in args[1]

    assert mock_notify_command.call_count == 2
    assert mock_notify_model.call_count == 1
    project.refresh_from_db()
    assert project.demarches_simplifiees_date_depot == datetime.datetime(
        2025, 1, 29, 15, 25, 3, tzinfo=datetime.timezone.utc
    )
    assert project.demarches_simplifiees_last_sync is not None
    assert mock_post.call_count == 2
    assert "date=2025-01-29" in project.moulinette_url


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.models.notify")
@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_dossier_submission_admin_alert_ignores_expired_config(
    mock_post, mock_notify_command, mock_notify_model
):
    """The command should not process expired configs."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    # Expired config — should be ignored by the command
    DCConfigHaieFactory(
        validity_range=DateRange(one_year_ago, today, "[)"),
    )

    PetitionProjectFactory()
    call_command("dossier_submission_admin_alert")

    # The DS API should never be called since no valid config exists
    mock_post.assert_not_called()
