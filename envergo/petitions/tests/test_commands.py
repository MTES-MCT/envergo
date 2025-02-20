from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = pytest.mark.django_db


@patch("envergo.petitions.management.commands.dossier_submission_admin_alert.notify")
@patch("requests.post")
def test_dossier_submission_admin_alert(mock_post, mock_notify):
    # Define the first mock response
    mock_response_1 = Mock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {
        "data": {
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
                            "state": "en_construction",
                        },
                        {
                            "number": 123,
                            "state": "en_construction",
                            "champs": [
                                {
                                    "id": "ABC123",
                                    "label": "Url du simulateur",
                                    "stringValue": "",
                                },
                            ],
                        },
                    ],
                },
            }
        }
    }

    # Define the second mock response
    mock_response_2 = Mock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {
        "data": {
            "demarche": {
                "title": "(test) Guichet unique de la haie / Demande d'autorisation",
                "number": 103363,
                "dossiers": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [],
                },
            }
        }
    }

    mock_post.side_effect = [mock_response_1, mock_response_2]
    PetitionProjectFactory()
    ConfigHaieFactory()
    call_command("dossier_submission_admin_alert")

    args, kwargs = mock_notify.call_args_list[0]
    assert "Un dossier a été soumis sur Démarches Simplifiées" in args[0]
    assert "haie" in args[1]

    args, kwargs = mock_notify.call_args_list[1]
    assert (
        "Un dossier a été déposé sur démarches-simplifiées, qui ne correspond à aucun projet dans la base du GUH."
        in args[0]
    )
    assert "haie" in args[1]

    assert mock_notify.call_count == 2
