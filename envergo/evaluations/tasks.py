import json
import logging
from collections import defaultdict
from smtplib import SMTPException
from urllib.error import HTTPError

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.serializers.json import Serializer as JSONSerializer
from django.template.loader import render_to_string
from django.urls import reverse
from requests import post

from config.celery_app import app
from envergo.confs.utils import get_setting
from envergo.evaluations.models import (
    USER_TYPES,
    Evaluation,
    EvaluationSnapshot,
    RecipientStatus,
    Request,
)
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
    notify(message_body, "amenagement")


@app.task(
    autoretry_for=(
        HTTPError,
        SMTPException,
    ),
    retry_backoff=True,
)
def confirm_request_to_requester(request_id, host):
    """Send a confirmation email to the requester."""

    logger.info(f"Sending confirmation email to requester {request_id}")
    request = Request.objects.filter(id=request_id).first()
    delay_mention = get_setting("evalreq_confirmation_email_delay_mention")
    user_emails = request.get_requester_emails()
    faq_url = reverse("faq")
    contact_url = reverse("contact_us")
    file_upload_url = request.upload_files_url
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
        subject="[Envergo] Votre demande d'avis réglementaire",
        body=txt_body,
        from_email=settings.FROM_EMAIL["amenagement"]["evaluations"],
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


@app.task(
    autoretry_for=(HTTPError,),
    retry_backoff=True,
)
def post_evalreq_to_automation(request_id, host):
    """Send request data to Make.com."""
    webhook_url = settings.MAKE_COM_WEBHOOK
    logger.info(f"Sending data to make.com {request_id} {host}")
    request = Request.objects.get(id=request_id)

    # We need to provide the previous requests count for every instructor email
    extra_data = {}
    if request.is_from_instructor():
        instructor_emails = request.urbanism_department_emails

        # Let's fetch all requests by one of the current instructors
        requests = Request.objects.filter(user_type=USER_TYPES.instructor).filter(
            urbanism_department_emails__overlap=instructor_emails
        )
        # and create an {email: count} dict
        # the `defaultdict` makes sure the default key value is initialized
        # Since we will count the current request as well, we initialize the count to -1
        request_history = defaultdict(lambda: -1)
        for req in requests:
            for email in req.urbanism_department_emails:
                if email in instructor_emails:
                    request_history[email] += 1
        extra_data["request_history"] = dict(request_history)

    # Extract the additional file urls
    # In local environment, this will return file paths
    # But in production, the S3 storage will return full urls
    files = request.additional_files.all()
    extra_data["files"] = [f.file.storage.url(f.file.name) for f in files]

    post_a_model_to_automation(request, webhook_url, **extra_data)


@app.task
def warn_admin_of_email_error(recipient_status_id):
    status = RecipientStatus.objects.select_related(
        "regulatory_notice_log__evaluation", "regulatory_notice_log__sender"
    ).get(id=recipient_status_id)

    log = status.regulatory_notice_log
    evaluation = log.evaluation
    evalreq = evaluation.request
    base_url = get_base_url(
        settings.ENVERGO_AMENAGEMENT_DOMAIN
    )  # Evaluations exist only for Envergo Amenagement.
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
        recipient_list=[settings.FROM_EMAIL["amenagement"]["default"]],
        from_email=settings.FROM_EMAIL["amenagement"]["admin"],
        fail_silently=False,
    )


@app.task
def post_evaluation_to_automation(evaluation_uid):
    """Send the edited evaluation data to a webhook."""
    webhook_url = settings.MAKE_COM_EVALUATION_EDITION_WEBHOOK
    evaluation = Evaluation.objects.get(uid=evaluation_uid)
    logger.info(f"Sending Evaluation to make.com {evaluation.reference}")
    extra_data = {}
    snapshot = (
        EvaluationSnapshot.objects.filter(evaluation=evaluation)
        .order_by("-created_at")
        .first()
    )
    if snapshot:
        extra_data["snapshot"] = snapshot.payload
    post_a_model_to_automation(evaluation, webhook_url, **extra_data)


def post_a_model_to_automation(model, webhook_url, **extra_data):
    serialized = BetterJsonSerializer().serialize([model])
    json_data = json.loads(serialized)[0]
    payload = json_data["fields"]
    payload["pk"] = json_data["pk"]
    payload.update(extra_data)

    logger.info("Posting info to make.com webhook")
    logger.info(payload)

    if webhook_url:
        res = post(webhook_url, json=payload)
        if res.status_code != 200:
            logger.error(f"Error while posting data to make.com: {res.text}")
    else:
        logger.warning("No make.com webhook configured. Doing nothing.")
