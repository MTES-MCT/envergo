import datetime
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.test import override_settings

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.services import (
    build_ds_details,
    fetch_project_details_from_demarches_simplifiees,
)
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


with open(
    Path(
        settings.APPS_DIR
        / "petitions"
        / "demarches_simplifiees"
        / "data"
        / "fake_dossier.json"
    ),
    "r",
) as file:
    GET_DOSSIER_FAKE_RESPONSE = json.load(file)


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees(mock_post, haie_user, site):
    """Test fetch project details from démarches simplifiées"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = GET_DOSSIER_FAKE_RESPONSE
    mock_post.return_value = mock_response

    config = ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()

    dossier = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )
    assert dossier is not None

    details = build_ds_details(petition_project, config, site, "", haie_user)

    assert details.applicant_name == "Mme Lamarr Hedy"
    assert details.city == "Laon (02000)"
    assert details.pacage == "123456789"

    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_date_depot == datetime.datetime(
        2025, 3, 21, 10, 8, 34, tzinfo=datetime.timezone.utc
    )
    assert petition_project.demarches_simplifiees_last_sync is not None


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_not_enabled(
    mock_post, caplog, haie_user, site
):
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
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
    fake_dossier = GET_DOSSIER_FAKE_RESPONSE.get("data", {}).get("dossier")
    assert details.usager == fake_dossier.get("usager").get("email")


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
