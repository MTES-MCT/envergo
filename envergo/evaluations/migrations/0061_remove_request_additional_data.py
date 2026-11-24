import logging
from os.path import basename

from django.core.files import File
from django.db import migrations

logger = logging.getLogger(__name__)


def move_additional_data_to_request_files(apps, schema_editor):
    """Copy each request's additional data file into a RequestFile.

    Both fields use different storages, so the file content is copied, not
    just its name. Source files are kept in place.
    """
    Request = apps.get_model("evaluations", "Request")
    RequestFile = apps.get_model("evaluations", "RequestFile")

    requests = Request.objects.exclude(additional_data="").exclude(
        additional_data__isnull=True
    )
    for request in requests:
        source = request.additional_data
        name = basename(source.name)
        if not source.storage.exists(source.name):
            logger.warning(
                f"Missing additional data file {source.name} for request {request.reference}."
            )
            continue

        request_file = RequestFile(
            request=request, name=name, uploaded_at=request.created_at
        )
        with source.open("rb") as content:
            request_file.file.save(name, File(content), save=True)


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0060_delete_recipientstatus"),
    ]

    operations = [
        migrations.RunPython(
            move_additional_data_to_request_files, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="request",
            name="additional_data",
        ),
    ]
