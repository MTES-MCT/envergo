from datetime import date

from django.conf import settings

from config.celery_app import app
from envergo.petitions.models import PetitionProject, StatusLog
from envergo.petitions.services import (
    declaration_receipt_message,
    send_message_dossier_ds,
)


@app.task
def send_closing_message_async(status_log_id):
    """Send the closing message to the applicant via the DS messagerie."""
    if not settings.DEMARCHE_NUMERIQUE["ENABLED"]:
        return

    log = StatusLog.objects.select_related("petition_project").get(pk=status_log_id)

    attachment = None
    if log.prefectural_order:
        log.prefectural_order.open()
        attachment = log.prefectural_order

    response = send_message_dossier_ds(
        log.petition_project, log.applicant_message, attachment
    )
    if response is None or response.get("errors") is not None:
        raise RuntimeError(f"DS closing message failed for StatusLog {status_log_id}")


@app.task
def send_declaration_receipt_async(project_id, received_on_iso, due_date_iso):
    """Send the déclaration receipt to the applicant via the DS messagerie."""
    if not settings.DEMARCHE_NUMERIQUE["ENABLED"]:
        return

    project = (
        PetitionProject.objects.select_related("department")
        .defer("department__geometry")
        .get(pk=project_id)
    )
    received_on = date.fromisoformat(received_on_iso)
    due_date = date.fromisoformat(due_date_iso)

    message = declaration_receipt_message(project, received_on, due_date)

    response = send_message_dossier_ds(project, message)
    if response is None or response.get("errors") is not None:
        raise RuntimeError(
            f"DS declaration receipt failed for project {project.reference}"
        )
