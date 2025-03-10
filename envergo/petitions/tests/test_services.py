from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.services import fetch_project_details_from_demarches_simplifiees
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees(mock_post, haie_user, site):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "dossier": {
                "id": "RG9zc2llci0yMTY4MzczOQ==",
                "number": 21683739,
                "state": "en_construction",
                "usager": {"email": "pierre-yves.dezaunay@beta.gouv.fr"},
                "demandeur": {
                    "civilite": "Mme",
                    "nom": "dez",
                    "prenom": "dez",
                    "email": None,
                },
                "champs": [
                    {"id": "Q2hhbXAtNDUzNDEzNQ==", "stringValue": ""},
                    {
                        "id": "Q2hhbXAtNDcyOTE3MA==",
                        "stringValue": "Agriculteur, agricultrice",
                    },
                    {"id": "Q2hhbXAtNDcyOTE3MQ==", "stringValue": "terminator"},
                    {
                        "id": "Q2hhbXAtNDUzNDE0NA==",
                        "stringValue": "27 Route de Cantois 33760 Ladaux",
                    },
                    {"id": "Q2hhbXAtNDUzNDE0NQ==", "stringValue": "test@test.fr"},
                    {"id": "Q2hhbXAtNDU0MzkzMg==", "stringValue": "06 12 34 56 78"},
                    {"id": "Q2hhbXAtNDU0MzkzOA==", "stringValue": "123456789"},
                    {"id": "Q2hhbXAtNDUzNDE1Ng==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDc0NDcyMQ==", "stringValue": ""},
                    {
                        "id": "Q2hhbXAtNDU0Mzk0Mw==",
                        "stringValue": "http://haie.local:3000/projet/E6Y6E9",
                    },
                    {"id": "Q2hhbXAtNDcyOTE4Nw==", "stringValue": "Ladaux (33760)"},
                    {"id": "Q2hhbXAtNDUzNDE0Ng==", "stringValue": "sdf"},
                    {"id": "Q2hhbXAtNDcyOTE3NQ==", "stringValue": "sdf"},
                    {"id": "Q2hhbXAtNDcyOTE3Ng==", "stringValue": "dsf"},
                    {"id": "Q2hhbXAtNDcyOTE3Nw==", "stringValue": "dsf"},
                    {"id": "Q2hhbXAtNDcyOTE4OA==", "stringValue": None},
                    {"id": "Q2hhbXAtNDcyOTE3OA==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDcyOTE3OQ==", "stringValue": "true"},
                    {"id": "Q2hhbXAtNDU5NjU1Mw==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDcyOTI4NA==", "stringValue": "true"},
                    {
                        "id": "Q2hhbXAtNDU1OTU2Mw==",
                        "stringValue": "Réhabilitation d’un fossé",
                    },
                    {"id": "Q2hhbXAtNDcyOTE4NQ==", "stringValue": "xcb"},
                    {"id": "Q2hhbXAtNDcyOTE4Ng==", "stringValue": "xvcb"},
                    {"id": "Q2hhbXAtNDU5NjU2NA==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDcyOTIwMQ==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDU5Nzc0Mw==", "stringValue": "xcvb"},
                    {"id": "Q2hhbXAtNDcyOTIwMg==", "stringValue": "Moins de 25 ans"},
                    {"id": "Q2hhbXAtNDcyOTIwMw==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDcyOTI4Mg==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDcyOTIwNg==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDcyOTIwOQ==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDcyOTIxMQ==", "stringValue": "Plus rarement"},
                    {"id": "Q2hhbXAtNDcyOTIxMg==", "stringValue": "xcv"},
                    {"id": "Q2hhbXAtNDcyOTIxMw==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDcyOTIxNA==", "stringValue": "xcv"},
                    {"id": "Q2hhbXAtNDcyOTIxNQ==", "stringValue": "xcvb"},
                    {"id": "Q2hhbXAtNDcyOTIxNg==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDcyOTIxOA==", "stringValue": "xcvb"},
                    {"id": "Q2hhbXAtNDcyOTIxOQ==", "stringValue": "xcvb"},
                    {"id": "Q2hhbXAtNDcyOTIyMA==", "stringValue": "xcvb"},
                    {"id": "Q2hhbXAtNDcyOTIyMQ==", "stringValue": "false"},
                    {"id": "Q2hhbXAtNDU1OTU0Nw==", "stringValue": ""},
                    {"id": "Q2hhbXAtNDcyOTIyNA==", "stringValue": "true"},
                    {"id": "Q2hhbXAtNDcyOTI4Mw==", "stringValue": "true"},
                ],
            }
        }
    }

    mock_post.return_value = mock_response
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details.applicant_name == "Mme dez dez"
    assert details.city == "Ladaux (33760)"
    assert details.pacage == "123456789"


@patch("envergo.petitions.services.notify")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_if_config_is_incomplete(
    mock_notify, haie_user, site
):
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "Les identifiants des champs PACAGE et Commune principale ne sont pas renseignés"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.services.notify")
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_API_error(
    mock_post, mock_notify, haie_user, site
):
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"an error": "occurred"}

    mock_post.return_value = mock_response
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.services.notify")
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_unexpected_response(
    mock_post, mock_notify, haie_user, site
):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"weirdely_formatted": "response"}}

    mock_post.return_value = mock_response
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu."
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()
