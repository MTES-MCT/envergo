"""Rename HostedFile paths from f/ to documents/ and rewrite hardcoded S3 URLs.

The schema migration 0008 changed upload_to from "f" to "documents", but
existing records still have the old prefix. This migration updates them.

It also rewrites the ~43 hardcoded S3 URLs in moulinette templates and
config fields to use the stable /fichiers/ path.
"""

import re

from django.conf import settings
from django.db import migrations

# Old S3 URL patterns found in the database.
S3_URL_PATTERNS = [
    # HostedFile URLs (most common)
    re.compile(
        r"https://envergo-stage\.s3\.fr-par\.scw\.cloud/envergo-stage/media/f/([^\s\"'<>)]+)"
    ),
    # Legacy prefix (5 files)
    re.compile(
        r"https://envergo-stage\.s3\.fr-par\.scw\.cloud/envergo-media-prod/([^\s\"'<>)]+)"
    ),
]


def get_stable_url(filename):
    domain = getattr(settings, "ENVERGO_AMENAGEMENT_DOMAIN", "envergo.beta.gouv.fr")
    return f"https://{domain}/fichiers/documents/{filename}"


def rewrite_s3_urls(text):
    for pattern in S3_URL_PATTERNS:
        text = pattern.sub(lambda m: get_stable_url(m.group(1)), text)
    return text


def rename_hosted_file_paths(apps, schema_editor):
    HostedFile = apps.get_model("confs", "HostedFile")
    for hf in HostedFile.objects.filter(file__startswith="f/"):
        hf.file.name = "documents/" + hf.file.name.removeprefix("f/")
        hf.save(update_fields=["file"])


def rewrite_moulinette_template_urls(apps, schema_editor):
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")
    for tpl in MoulinetteTemplate.objects.filter(content__contains="envergo-stage"):
        new_content = rewrite_s3_urls(tpl.content)
        if new_content != tpl.content:
            tpl.content = new_content
            tpl.save(update_fields=["content"])


CONFIG_TEXT_FIELDS = [
    "lse_contact_ddtm",
    "n2000_contact_ddtm_info",
    "n2000_contact_ddtm_instruction",
    "n2000_procedure_ein",
    "n2000_lotissement_proximite",
    "lse_free_mention",
    "ep_free_mention",
    "evalenv_procedure_casparcas",
]


def rewrite_config_amenagement_urls(apps, schema_editor):
    ConfigAmenagement = apps.get_model("moulinette", "ConfigAmenagement")
    for config in ConfigAmenagement.objects.all():
        changed = False
        for field_name in CONFIG_TEXT_FIELDS:
            value = getattr(config, field_name, None)
            if value and "envergo-stage" in value:
                new_value = rewrite_s3_urls(value)
                if new_value != value:
                    setattr(config, field_name, new_value)
                    changed = True
        if changed:
            config.save(update_fields=CONFIG_TEXT_FIELDS)


def forwards(apps, schema_editor):
    rename_hosted_file_paths(apps, schema_editor)
    rewrite_moulinette_template_urls(apps, schema_editor)
    rewrite_config_amenagement_urls(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("confs", "0008_hosted_file_public_storage"),
        ("moulinette", "0132_merge_20260729_1142"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
