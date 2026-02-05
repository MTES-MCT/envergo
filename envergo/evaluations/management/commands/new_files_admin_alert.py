from datetime import timedelta
from itertools import groupby

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime

from envergo.evaluations.models import Request, RequestFile
from envergo.utils.mattermost import notify


def is_file_uploaded_from_admin(file, logs_from_admin):
    """Check if the file was uploaded from the admin UI."""
    return any(
        f"RequestFile object ({file.id})" in log_entry.change_message
        for log_entry in logs_from_admin
    )


class Command(BaseCommand):
    help = "Post a message when a an evalreq, that has already been converted into an evaluation, has a new file."

    def handle(self, *args, **options):

        # We want to notify admins every time a Request has a new file.
        # But we don't want to spam a message for each and every file.
        # Hence, we wait for an hour, then we send a single message for each Request that has new files.
        # We also don't want to send a notification if the evalreq was just created.
        # So we only select files that were uploaded more than 1hr after the evalreq was created.
        one_hr_ago = localtime() - timedelta(hours=1)
        two_hours_ago = localtime() - timedelta(hours=2)
        one_hour_delta = timedelta(hours=1)

        files = (
            RequestFile.objects.filter(request__evaluation__isnull=False)
            .filter(uploaded_at__gte=two_hours_ago)
            .filter(uploaded_at__lt=one_hr_ago)
            .annotate(upload_delta=F("uploaded_at") - F("request__created_at"))
            .filter(upload_delta__gte=one_hour_delta)
            .order_by("request")
            .select_related("request__evaluation")
        )
        groups = groupby(files, key=lambda file: file.request)

        content_type = ContentType.objects.get_for_model(Request)
        for request, files_iter in groups:
            files = list(files_iter)

            # if the files were uploaded from the admin ui, we don't want to notify
            logs_from_admin = LogEntry.objects.filter(
                content_type=content_type,
                object_id=request.id,
                action_time__gte=two_hours_ago,
            )
            if all(
                is_file_uploaded_from_admin(file, logs_from_admin) for file in files
            ):
                continue

            url = reverse("admin:evaluations_request_change", args=[request.id])
            eval_url = reverse(
                "admin:evaluations_evaluation_change", args=[request.evaluation.uid]
            )

            message = render_to_string(
                "evaluations/edit_eval_request_notification.txt",
                context={
                    "url": url,
                    "eval_url": eval_url,
                    "request": request,
                    "files_number": len(list(files)),
                    "ops": ", ".join(settings.OPS_MATTERMOST_HANDLERS),
                },
            )
            notify(message, "amenagement")
