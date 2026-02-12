from datetime import timedelta
from itertools import groupby

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime

from envergo.evaluations.models import RequestFile
from envergo.evaluations.tasks import post_evalreq_to_automation
from envergo.utils.tools import get_base_url


class Command(BaseCommand):
    help = "Post a message when an evalreq has a new file."

    def handle(self, *args, **options):

        base_url = get_base_url(settings.ENVERGO_AMENAGEMENT_DOMAIN)

        # We want to notify users when they uploaded a new file.
        # Wait 15 minutes after the last uploaded file to send a notification.
        a_quarter_hr_ago = localtime() - timedelta(minutes=15)
        half_hour_ago = localtime() - timedelta(minutes=30)

        files = (
            RequestFile.objects.filter(uploaded_at__gte=half_hour_ago)
            .filter(uploaded_at__lte=a_quarter_hr_ago)
            .filter(request__created_at__lte=half_hour_ago)
            .order_by("request")
            .select_related("request")
        )
        groups = groupby(files, key=lambda file: file.request)
        for request, files in groups:
            emails = request.get_requester_emails()
            faq_url = reverse("faq")
            contact_url = reverse("contact_us")
            file_upload_url = request.upload_files_url
            context = {
                "reference": request.reference,
                "address": request.address,
                "application_number": request.application_number,
                "faq_url": f"{base_url}{faq_url}",
                "contact_url": f"{base_url}{contact_url}",
                "file_upload_url": f"{base_url}{file_upload_url}",
            }
            txt_body = render_to_string(
                "evaluations/emails/new_files_user_alert.txt", context=context
            )
            html_body = render_to_string(
                "evaluations/emails/new_files_user_alert.html", context=context
            )

            email = EmailMultiAlternatives(
                subject="[Envergo] Votre mise à jour de documents",
                body=txt_body,
                from_email=settings.FROM_EMAIL["amenagement"]["evaluations"],
                to=emails,
            )
            email.attach_alternative(html_body, "text/html")
            email.send()

            # Trigger webhook to Make.com
            post_evalreq_to_automation.delay(request.id, base_url)
