from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.evaluations.models import Request
from envergo.utils.mattermost import notify


@app.task
def confirm_request_to_admin(request_id, host):
    """Send a Mattermost notification to confirm the evaluation request."""

    request = Request.objects.get(id=request_id)
    request_url = reverse("admin:evaluations_request_change", args=[request_id])
    parcel_map_url = request.get_parcel_map_url()
    message_body = render_to_string(
        "evaluations/eval_request_notification.txt",
        context={
            "request": request,
            "request_url": f"https://{host}{request_url}",
            "parcel_map_url": f"https://{host}{parcel_map_url}",
        },
    )
    notify(message_body)


@app.task
def confirm_request_to_requester(request_id):
    request = Request.objects.filter(id=request_id).first()
    user_email = request.contact_email
    email_body = render_to_string("evaluations/emails/request_confirm_body.txt")

    email = EmailMessage(
        subject="Votre demande d'évaluation",
        body=email_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
        bcc=[settings.DEFAULT_FROM_EMAIL],
    )
    email.send()
