from datetime import timedelta
from itertools import groupby

from django.core.management.base import BaseCommand
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
        one_hr_ago = localtime() - timedelta(hours=1)
        two_ours_ago = localtime() - timedelta(hours=2)

        files = (
            RequestFile.objects.filter(uploaded_at__gte=two_ours_ago)
            .filter(uploaded_at__lt=one_hr_ago)
            .order_by("request")
            .select_related("request")
        )
        groups = groupby(files, key=lambda file: file.request)
        for request, files in groups:
            url = reverse("admin:evaluations_request_change", args=[request.id])
            message = f"""
            Une demande d'avis a été mise à jour.
            Adresse : {request.address}
            {len(list(files))} nouveaux fichiers ont été ajoutés.
            [Admin django](https://envergo.beta.gouv.fr/{url})
            """
            notify(message)
