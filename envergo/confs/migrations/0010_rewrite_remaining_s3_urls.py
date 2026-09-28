"""Rewrite hardcoded S3 URLs in the fields missed by migration 0009.

A full scan of every text column in the production database surfaced
hosted-file S3 URLs in these additional fields:
- moulinette Criterion.header
- moulinette ConfigHaie.contacts_and_links / natura2000_coordinators_list_url
- geodata Map.description
- evaluations EvaluationVersion.content (frozen legal snapshots: only the
  link targets change, the referenced documents are byte-identical)
"""

import re

from django.conf import settings
from django.db import migrations

# Same patterns as migration 0009.
S3_URL_PATTERNS = [
    re.compile(
        r"https://envergo-stage\.s3\.fr-par\.scw\.cloud/envergo-stage/media/f/([^\s\"'<>)]+)"
    ),
    re.compile(
        r"https://envergo-stage\.s3\.fr-par\.scw\.cloud/envergo-media-prod/([^\s\"'<>)]+)"
    ),
]

# (app_label, model_name, [field, ...]) triples to rewrite.
REWRITE_TARGETS = [
    ("moulinette", "Criterion", ["header"]),
    ("moulinette", "ConfigHaie", ["contacts_and_links", "natura2000_coordinators_list_url"]),
    ("geodata", "Map", ["description"]),
    ("evaluations", "EvaluationVersion", ["content"]),
]


def get_stable_url(filename):
    domain = getattr(settings, "ENVERGO_AMENAGEMENT_DOMAIN", "envergo.beta.gouv.fr")
    return f"https://{domain}/fichiers/documents/{filename}"


def rewrite_s3_urls(text):
    for pattern in S3_URL_PATTERNS:
        text = pattern.sub(lambda m: get_stable_url(m.group(1)), text)
    return text


def forwards(apps, schema_editor):
    from django.db.models import Q

    for app_label, model_name, fields in REWRITE_TARGETS:
        model = apps.get_model(app_label, model_name)
        candidates = Q()
        for field_name in fields:
            candidates |= Q(**{f"{field_name}__contains": "envergo-stage"})
        for obj in model.objects.filter(candidates):
            changed_fields = []
            for field_name in fields:
                value = getattr(obj, field_name, None)
                if value:
                    new_value = rewrite_s3_urls(value)
                    if new_value != value:
                        setattr(obj, field_name, new_value)
                        changed_fields.append(field_name)
            if changed_fields:
                obj.save(update_fields=changed_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("confs", "0009_migrate_hosted_file_paths_and_urls"),
        ("geodata", "0032_alter_map_map_type"),
        ("evaluations", "0060_delete_recipientstatus"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
