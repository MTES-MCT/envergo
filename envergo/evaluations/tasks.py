import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.evaluations.models import Request
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


@app.task
def confirm_request_to_admin(request_id, host):
    """Send a Mattermost notification to confirm the evaluation request."""

    logger.warning(f"[mattermost] Sending notification {request_id} {host}")
    request = Request.objects.get(id=request_id)
    logger.warning(f"[mattermost] Request {request}")
    request_url = reverse("admin:evaluations_request_change", args=[request_id])
    logger.warning(f"[mattermost] Request url {request_url}")
    parcel_map_url = request.get_parcel_map_url()
    logger.warning(f"[mattermost] Parcel map url {parcel_map_url}")
    message_body = render_to_string(
        "evaluations/eval_request_notification.txt",
        context={
            "request": request,
            "request_url": f"https://{host}{request_url}",
            "parcel_map_url": f"https://{host}{parcel_map_url}",
        },
    )
    logger.warning(f"[mattermost] message body {message_body}")
    notify(message_body)


@app.task
def confirm_request_to_requester(request_id):
    request = Request.objects.filter(id=request_id).first()
    user_email = request.contact_email
    context = {"application_number": request.application_number}
    txt_body = render_to_string(
        "evaluations/emails/request_confirm_body.txt", context=context
    )
    html_body = render_to_string(
        "evaluations/emails/request_confirm_body.html", context=context
    )

    email = EmailMultiAlternatives(
        subject="[EnvErgo] Votre demande d'évaluation Loi sur l'Eau",
        body=txt_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
        bcc=[settings.DEFAULT_FROM_EMAIL],
    )
    email.attach_alternative(html_body, "text/html")
    email.send()
