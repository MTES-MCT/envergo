import json
import logging

import requests
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core import mail
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.serializers.json import Serializer as JSONSerializer
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.evaluations.models import Evaluation, RecipientStatus, Request
from envergo.users.models import User
from envergo.utils.mattermost import notify
from envergo.utils.tools import get_base_url

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
def confirm_request_to_requester(request_id, host):
    request = Request.objects.filter(id=request_id).first()
    user_emails = request.contact_emails
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
        subject="[EnvErgo] Votre demande d'avis réglementaire",
        body=txt_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=user_emails,
    )
    email.attach_alternative(html_body, "text/html")
    email.send()


@app.task
def share_evaluation_by_email(evaluation_reference, host, sender_id, emails):
    user = User.objects.get(id=sender_id)
    evaluation = Evaluation.objects.get(reference=evaluation_reference)
    subject = "[EnvErgo] Simulation réglementaire"
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


class BetterJsonSerializer(JSONSerializer):
    """Serialize django model objects to json.

    There is a problem with the default json serializer, where
    ArrayField instances are serialized to a single string instead of
    an array of value. This class fixes this issue.
    """

    def handle_field(self, obj, field):
        if isinstance(field, ArrayField):
            self._current[field.name] = getattr(obj, field.name)
        else:
            super().handle_field(obj, field)


@app.task
def post_evalreq_to_automation(request_id, host):
    """Send request data to Make.com."""

    webhook_url = settings.MAKE_COM_WEBHOOK
    if not webhook_url:
        logger.warning("No make.com webhook configured. Doing nothing.")
        return

    logger.info(f"Sending data to make.com {request_id} {host}")
    request = Request.objects.get(id=request_id)
    serialized = BetterJsonSerializer().serialize([request])
    json_data = json.loads(serialized)[0]
    payload = json_data["fields"]
    payload["pk"] = json_data["pk"]

    res = requests.post(webhook_url, json=payload)
    if res.status_code != 200:
        logger.error(f"Error while posting data to make.com: {res.text}")


@app.task
def warn_admin_of_email_error(recipient_status_id):
    status = RecipientStatus.objects.select_related(
        "regulatory_notice_log__evaluation", "regulatory_notice_log__sender"
    ).get(id=recipient_status_id)

    log = status.regulatory_notice_log
    evaluation = log.evaluation
    evalreq = evaluation.request
    base_url = get_base_url()
    eval_url = reverse(
        "admin:evaluations_evaluation_change",
        args=[evaluation.reference],
    )
    full_eval_url = f"{base_url}{eval_url}"

    context = {
        "status": status,
        "evaluation": evaluation,
        "log": log,
        "eval_url": full_eval_url,
    }
    template = "admin/evaluations/emails/eval_email_error.txt"
    body = render_to_string(template, context)
    send_mail(
        f"⚠️ [{evalreq.id}] Erreur d'envoi email AR",
        body,
        recipient_list=[settings.DEFAULT_FROM_EMAIL],
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=False,
    )
