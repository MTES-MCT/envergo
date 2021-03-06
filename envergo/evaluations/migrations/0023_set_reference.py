# Generated by Django 3.2.6 on 2021-09-24 08:24

import secrets

from django.conf import settings
from django.db import migrations
from django.db.migrations.operations.special import RunPython


def generate_reference():
    """Generate a short random and readable reference."""

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    length = 6
    reference = "".join(secrets.choice(alphabet) for i in range(length))

    return reference


def set_references(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    for evaluation in Evaluation.objects.all():
        evaluation.reference = generate_reference()
        evaluation.save()

    Request = apps.get_model("evaluations", "request")
    for request in Request.objects.all():
        request.reference = generate_reference()
        request.save()


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0022_auto_20210924_0823"),
    ]

    operations = [migrations.RunPython(set_references, migrations.RunPython.noop)]
