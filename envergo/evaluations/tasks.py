from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.evaluations.models import Request
from envergo.utils.mattermost import notify


@app.task
def confirm_request_to_admin(request_id, host):
    request_url = reverse("admin:evaluations_request_change", args=[request_id])
    msg = f"Une nouvelle évaluation a été demandée. https://{host}{request_url}"
    notify(msg)


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
