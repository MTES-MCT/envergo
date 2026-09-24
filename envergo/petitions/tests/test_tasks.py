from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from envergo.moulinette.tests.factories import RUConfigHaieFactory
from envergo.petitions.tasks import (
    send_closing_message_async,
    send_declaration_receipt_async,
)
from envergo.petitions.tests.factories import (
    DEMARCHE_NUMERIQUE_FAKE,
    DEMARCHE_NUMERIQUE_FAKE_DISABLED,
    DOSSIER_SEND_MESSAGE_FAKE_RESPONSE,
    PetitionProjectFactory,
    StatusLogFactory,
)

pytestmark = pytest.mark.django_db


def closing_log(**kwargs):
    project = PetitionProjectFactory()
    return StatusLogFactory(
        petition_project=project,
        stage="closed",
        decision="tacit_agreement",
        applicant_message="Une décision a été rendue concernant votre dossier.",
        **kwargs,
    )


def ru_project():
    """A régime unique project, the only kind that gets a déclaration receipt."""
    RUConfigHaieFactory()
    return PetitionProjectFactory()


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_closing_message_without_attachment(mock_ds_msg):
    mock_ds_msg.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    log = closing_log()

    send_closing_message_async(log.pk)

    assert mock_ds_msg.call_count == 1
    args = mock_ds_msg.call_args[0]
    assert args[0] == log.petition_project
    assert args[1] == log.applicant_message
    assert args[2] is None


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_closing_message_with_attachment(mock_ds_msg):
    mock_ds_msg.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    log = closing_log(
        prefectural_order=SimpleUploadedFile("arrete.pdf", b"%PDF-1.4 fake")
    )

    send_closing_message_async(log.pk)

    attachment = mock_ds_msg.call_args[0][2]
    assert attachment is not None
    assert attachment.read() == b"%PDF-1.4 fake"


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE_DISABLED)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_closing_message_with_ds_disabled(mock_ds_msg):
    """When the DS API is disabled (dev), the task does nothing."""
    log = closing_log()

    send_closing_message_async(log.pk)

    assert not mock_ds_msg.called


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_closing_message_failure_raises_for_retry(mock_ds_msg):
    mock_ds_msg.return_value = None
    log = closing_log()

    with pytest.raises(RuntimeError):
        send_closing_message_async(log.pk)


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_declaration_receipt(mock_ds_msg):
    mock_ds_msg.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    project = ru_project()

    send_declaration_receipt_async(project.pk, "2026-10-05", "2026-12-05")

    assert mock_ds_msg.call_count == 1
    sent_project, message = mock_ds_msg.call_args[0]
    assert sent_project == project
    assert message.startswith("**Récépissé de déclaration**")
    assert "réceptionnée le 5 octobre 2026" in message
    assert "avant le 5 décembre 2026" in message


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE_DISABLED)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_declaration_receipt_with_ds_disabled(mock_ds_msg):
    """When the DS API is disabled (dev), the task does nothing."""
    project = ru_project()

    send_declaration_receipt_async(project.pk, "2026-10-05", "2026-12-05")

    assert not mock_ds_msg.called


@override_settings(DEMARCHE_NUMERIQUE=DEMARCHE_NUMERIQUE_FAKE)
@patch("envergo.petitions.tasks.send_message_dossier_ds")
def test_send_declaration_receipt_failure_raises_for_retry(mock_ds_msg):
    mock_ds_msg.return_value = None
    project = ru_project()

    with pytest.raises(RuntimeError):
        send_declaration_receipt_async(project.pk, "2026-10-05", "2026-12-05")
