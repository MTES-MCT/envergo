"""Data migration moved into 0111 — kept as empty migration to preserve the dependency chain."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0111_update_coeff_compensation_constraint"),
    ]

    operations = []
