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
                                "hasNextPage": False,
                                "endCursor": "MjAyNC0xMS0xOVQxMDoyMzowMy45NTc0NDAwMDBaOzIxMDU5Njc1",
                            },
                            "nodes": [
                                {
                                    "number": 21059675,
                                    "state": "en_construction",
                                    "champs": [
                                        {
                                            "id": "Q2hhbXAtNDUzNDEzNQ==",
                                            "label": "Identité",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDUzNDE0NQ==",
                                            "label": "Adresse email",
                                            "stringValue": "test@test.fr",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU0MzkzMg==",
                                            "label": "Numéro de téléphone",
                                            "stringValue": "06 12 23 45 56",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDUzNDE0NA==",
                                            "label": "Adresse postale",
                                            "stringValue": "Rue du Puits de Tet 21160 Marsannay-la-Côte",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU0Mzk2MQ==",
                                            "label": "J'effectue cette demande en tant que",
                                            "stringValue": "Autre (collectivité, aménageur, gestionnaire de réseau,"
                                            " particulier, etc.)",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU0MzkzNA==",
                                            "label": "Numéro Siret",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDUzNDE0Mw==",
                                            "label": "Raison sociale",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDUzNDE1Ng==",
                                            "label": "Description du projet",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDUzNDE0Ng==",
                                            "label": "Expliquez le contexte et les objectifs de votre projet",
                                            "stringValue": "dgdfg",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU5NjU1Mw==",
                                            "label": "Conditionnalité PAC - BCAE8",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU1OTU2Mw==",
                                            "label": "(NE PAS MODIFIER) Instruction Conditionnalité PAC - BCAE8",
                                            "stringValue": "false",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU5NjU2NA==",
                                            "label": "Biodiversité",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU1OTU2OQ==",
                                            "label": '(NE PAS MODIFIER) Instruction dérogation "espèces protégées"',
                                            "stringValue": "false",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU5NzUwMw==",
                                            "label": "(NE PAS MODIFIER) Instruction Natura 2000",
                                            "stringValue": "true",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU1OTU0Mw==",
                                            "label": "Informations réservées à l'administration",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU1OTU0Nw==",
                                            "label": "Cette section est réservée à l'administration",
                                            "stringValue": "",
                                            "prefilled": False,
                                        },
                                        {
                                            "id": "Q2hhbXAtNDU0Mzk0Mw==",
                                            "label": "(NE PAS MODIFIER) URL simulation",
                                            "stringValue": "https://haie.incubateur.net/simulateur/resultat/?profil="
                                            "autre&motif=autre&reimplantation=non&haies=7d9b0b87-3b9d-"
                                            "4300-bf36-ffadfff80283&travaux=destruction&department=02&"
                                            "element=haie",
                                            "prefilled": True,
                                        },
                                    ],
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
