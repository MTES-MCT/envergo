import json
import logging

import requests
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.serializers.json import Serializer as JSONSerializer
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.confs.utils import get_setting
from envergo.evaluations.models import Evaluation, RecipientStatus, Request
from envergo.utils.mattermost import notify
from envergo.utils.tools import get_base_url

logger = logging.getLogger(__name__)


@app.task(autoretry_for=(Exception,))
def confirm_request_to_admin(request_id, host):
    """Send a Mattermost notification to confirm the evaluation request."""

    logger.info(f"[mattermost] Sending notification {request_id} {host}")
    request = Request.objects.get(id=request_id)
    request_url = reverse("admin:evaluations_request_change", args=[request_id])
    message_body = render_to_string(
        "evaluations/eval_request_notification.txt",
        context={
            "request": request,
            "request_url": f"https://{host}{request_url}",
        },
    )
    logger.info(f"[mattermost] message body {message_body}")
    notify(message_body)


@app.task
def confirm_request_to_requester(request_id, host):
    """Send a confirmation email to the requester."""

    logger.info(f"Sending confirmation email to requester {request_id}")
    request = Request.objects.filter(id=request_id).first()
    delay_mention = get_setting("evalreq_confirmation_email_delay_mention")
    user_emails = request.urbanism_department_emails
    faq_url = reverse("faq")
    contact_url = reverse("contact_us")
    file_upload_url = reverse("request_eval_wizard_step_3", args=[request.reference])
    context = {
        "application_number": request.application_number,
        "delay_mention": delay_mention,
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
    logger.info("Sending now")
    res = email.send()
    logger.info(f"Sent {res}")


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
    logger.info(f"Sending data to make.com {request_id} {host}")
    request = Request.objects.get(id=request_id)
    post_a_model_to_automation(request, webhook_url)


@app.task
def warn_admin_of_email_error(recipient_status_id):
    status = RecipientStatus.objects.select_related(
        "regulatory_notice_log__evaluation", "regulatory_notice_log__sender"
    ).get(id=recipient_status_id)

    log = status.regulatory_notice_log
    evaluation = log.evaluation
    evalreq = evaluation.request
    base_url = get_base_url(evaluation.get_site().domain)
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


@app.task
def post_evaluation_to_automation(evaluation_uid):
    """Send the edited evaluation data to a webhook."""
    webhook_url = settings.MAKE_COM_EVALUATION_EDITION_WEBHOOK
    evaluation = Evaluation.objects.get(uid=evaluation_uid)
    logger.info(f"Sending Evaluation to make.com {evaluation.reference}")
    post_a_model_to_automation(evaluation, webhook_url)


def post_a_model_to_automation(model, webhook_url):
    if not webhook_url:
        logger.warning("No make.com webhook configured. Doing nothing.")
        return

    serialized = BetterJsonSerializer().serialize([model])
    json_data = json.loads(serialized)[0]
    payload = json_data["fields"]
    payload["pk"] = json_data["pk"]

    res = requests.post(webhook_url, json=payload)
    if res.status_code != 200:
        logger.error(f"Error while posting data to make.com: {res.text}")
