from unittest.mock import patch

import pytest
from django.core.management import call_command

from envergo.moulinette.tests.factories import ConfigHaieFactory

pytestmark = pytest.mark.django_db


@patch("envergo.evaluations.management.commands.new_files_admin_alert.notify")
@patch("requests.post")
def test_dossier_submission_admin_alert(mock_notify, mock_post):
    mock_post.return_value.status_code = 200
    mock_post.side_effect = [
        {
            "status_code": 200,
            "json": lambda: {
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
                                }
                            ],
                        },
                    }
                }
            },
        },
        {
            "status_code": 200,
            "json": lambda: {
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
            },
        },
    ]

    ConfigHaieFactory()
    call_command("dossier_submission_admin_alert")

    mock_notify.assert_called_once()
