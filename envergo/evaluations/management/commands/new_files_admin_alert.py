from datetime import timedelta
from itertools import groupby
from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import F
from django.urls import reverse
from django.utils.timezone import localtime

from envergo.evaluations.models import RequestFile
from envergo.utils.mattermost import notify


class Command(BaseCommand):
    help = "Post a message when a an evalreq has a new file."

    def handle(self, *args, **options):

        # We want to notify admins every time a Request has a new file.
        # But we don't want to spam a message for each and every file.
        # Hence, we wait for an hour, then we send a single message for each Request that has new files.
        # We also don't want to send a notification if the evalreq was just created.
        # So we only select files that were uploaded more than 1hr after the evalreq was created.
        one_hr_ago = localtime() - timedelta(hours=1)
        two_ours_ago = localtime() - timedelta(hours=2)
        one_hour_delta = timedelta(hours=1)

        files = (
            RequestFile.objects.filter(uploaded_at__gte=two_ours_ago)
            .filter(uploaded_at__lt=one_hr_ago)
            .annotate(upload_delta=F("uploaded_at") - F("request__created_at"))
            .filter(upload_delta__gte=one_hour_delta)
            .order_by("request")
            .select_related("request")
        )
        groups = groupby(files, key=lambda file: file.request)
        for request, files in groups:
            url = reverse("admin:evaluations_request_change", args=[request.id])
            message = dedent(
                f"""\
                **Une [demande d'avis](https://envergo.beta.gouv.fr{url}) a été mise à jour.**

                Adresse : {request.address}

                Date de la demande initiale : {request.created_at:%d/%m/%Y}

                {len(list(files))} nouveaux fichiers ont été ajoutés.

                ping {", ".join(settings.OPS_MATTERMOST_HANDLERS)}
                """
            )
            notify(message, "amenagement")
