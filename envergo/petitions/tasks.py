from django.conf import settings

from config.celery_app import app
from envergo.petitions.models import StatusLog
from envergo.petitions.services import send_message_dossier_ds


@app.task
def send_closing_message_async(status_log_id):
    """Send the closing message to the applicant via the DS messagerie.

    The message and its optional prefectural order attachment are read from
    the closing status log. Raises on failure so the default retry policy
    (see `config.celery_app.BaseTaskWithRetry`) replays the send.
    """
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
