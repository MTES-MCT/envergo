from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.petitions.models import PetitionProject, StatusLog
from envergo.petitions.services import (
    declaration_receipt_message,
    send_message_dossier_ds,
)
from envergo.petitions.templatetags.petitions import format_ds_number
from envergo.utils.tools import get_base_url


@app.task
def send_closing_message_async(status_log_id):
    """Send the closing message to the applicant via the DN messagerie."""
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
        raise RuntimeError(f"DN closing message failed for StatusLog {status_log_id}")


@app.task
def send_declaration_receipt_async(project_id, received_on_iso, due_date_iso):
    """Send the déclaration receipt to the applicant via the DN messagerie."""
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
            f"DN declaration receipt failed for project {project.reference}"
        )


@app.task
def send_new_dossier_email_async(project_id):
    """Tell the department's GUH mailbox about a new dossier, if it has one."""
    project = (
        PetitionProject.objects.select_related("department")
        .defer("department__geometry")
        .get(pk=project_id)
    )
    config = project.config
    if not config or not config.guh_email:
        return

    dossier_number = format_ds_number(project.demarche_numerique_dossier_number)
    base_url = get_base_url(settings.ENVERGO_HAIE_DOMAIN)
    instruction_path = reverse(
        "petition_project_summary",
        kwargs={"reference": project.reference},
        urlconf="config.urls_haie",
    )
    context = {
        "dossier_number": dossier_number,
        "instruction_url": f"{base_url}{instruction_path}",
    }

    txt_body = render_to_string("haie/emails/new_dossier.txt", context)
    html_body = render_to_string("haie/emails/new_dossier.html", context)
    send_mail(
        f"Guichet unique haie − Nouveau dossier déposé − n°{dossier_number}",
        txt_body,
        html_message=html_body,
        recipient_list=[config.guh_email],
        from_email=settings.FROM_EMAIL["haie"]["default"],
        fail_silently=False,
    )
