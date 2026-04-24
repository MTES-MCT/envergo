"""Shared conventions for Species stub objects.

When the RU CSV import creates a Species from a CD_REF alone, it uses
placeholder names because the CSV doesn't carry name data. These placeholders
are later replaced by import_taxref with real TaxRef data.

Both the creation side (tasks.py) and the enrichment side (import_taxref.py)
must agree on the placeholder format. This module is the single source of
truth for that convention.
"""

SCIENTIFIC_NAME_PLACEHOLDER_PREFIX = "CD_REF_"
COMMON_NAME_PLACEHOLDER_PREFIX = "Espèce "


def make_stub_scientific_name(cd_ref):
    """Build the placeholder scientific_name for a stub species."""
    return f"{SCIENTIFIC_NAME_PLACEHOLDER_PREFIX}{cd_ref}"


def make_stub_common_name(cd_ref):
    """Build the placeholder common_name for a stub species."""
    return f"{COMMON_NAME_PLACEHOLDER_PREFIX}{cd_ref}"


def has_placeholder_scientific_name(species):
    """Return True if the species has a placeholder scientific_name."""
    return species.scientific_name.startswith(SCIENTIFIC_NAME_PLACEHOLDER_PREFIX)


def has_placeholder_common_name(species):
    """Return True if the species has a placeholder or empty common_name."""
    return (
        not species.common_name
        or species.common_name.startswith(COMMON_NAME_PLACEHOLDER_PREFIX)
    )
