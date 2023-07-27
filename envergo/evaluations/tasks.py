import logging

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.evaluations.models import Evaluation, Request
from envergo.users.models import User
from envergo.utils.mattermost import notify
from envergo.utils.notion import post_request

logger = logging.getLogger(__name__)


@app.task(autoretry_for=(Exception,))
def confirm_request_to_admin(request_id, host):
    """Send a Mattermost notification to confirm the evaluation request."""

    logger.info(f"[mattermost] Sending notification {request_id} {host}")
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
    logger.info(f"[mattermost] message body {message_body}")
    notify(message_body)


@app.task
def post_request_to_notion(request_id, host):
    """Send request data to Notion."""

    logger.info(f"[notion] Sending notification {request_id} {host}")
    request = Request.objects.get(id=request_id)
    post_request(request, host)


@app.task
def confirm_request_to_requester(request_id, host):
    request = Request.objects.filter(id=request_id).first()
    user_email = request.contact_email
    faq_url = reverse("faq")
    contact_url = reverse("contact_us")
    file_upload_url = reverse("request_eval_wizard_step_3", args=[request.reference])
    context = {
        "application_number": request.application_number,
        "reference": request.reference,
        "faq_url": f"https://{host}{faq_url}",
        "contact_url": f"https://{host}{contact_url}",
        "file_upload_url": f"https://{host}{file_upload_url}",
    }
    txt_body = render_to_string(
        "evaluations/emails/request_confirm_body.txt", context=context
    )
    html_body = render_to_string(
        "evaluations/emails/request_confirm_body.html", context=context
    )

    email = EmailMultiAlternatives(
        subject="[EnvErgo] Suspension temporaire des services EnvErgo jusqu'au 28 août",
        body=txt_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
        bcc=[settings.DEFAULT_FROM_EMAIL],
    )
    email.attach_alternative(html_body, "text/html")
    email.send()


@app.task
def share_evaluation_by_email(evaluation_reference, host, sender_id, emails):
    user = User.objects.get(id=sender_id)
    evaluation = Evaluation.objects.get(reference=evaluation_reference)
    subject = "[EnvErgo] Évaluation Loi sur l'eau"
    url = reverse("evaluation_detail", args=[evaluation_reference])
    evaluation_url = f"https://{host}{url}?utm_medium=email"

    messages = []
    for email in emails:
        context = {
            "sender_email": user.email,
            "address": evaluation.address,
            "application_number": evaluation.application_number,
            "evaluation_url": evaluation_url,
        }
        txt_body = render_to_string(
            "evaluations/emails/share_evaluation_by_email_body.txt", context=context
        )
        html_body = render_to_string(
            "evaluations/emails/share_evaluation_by_email_body.html", context=context
        )
        message = EmailMultiAlternatives(subject, txt_body, to=[email])
        message.attach_alternative(html_body, "text/html")
        messages.append(message)

    connection = mail.get_connection()
    connection.send_messages(messages)
