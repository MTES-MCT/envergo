import json
import secrets
from collections import OrderedDict
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.sites.models import Site

if TYPE_CHECKING:
    from envergo.geodata.models import Department


def get_department_settings_form_url(department: "Department") -> str:
    """Build the Tally form url to update a department's contact info."""
    query = urlencode({"departement": department.get_department_display()})
    return f"https://tally.so/r/Pd9b9e?{query}"


def get_base_url(site_domain):
    scheme = "https"
    base_url = f"{scheme}://{site_domain}"
    return base_url


def get_site_literal(site: Site) -> Literal["haie", "amenagement"]:
    if site.domain == settings.ENVERGO_HAIE_DOMAIN:
        return "haie"

    return "amenagement"


def display_form_details(form):
    form_details = {"fields": {}, "errors": {}}

    for field in form:
        form_details["fields"][str(field.label)] = field.value()

    for field, errors in form.errors.items():
        form_details["errors"][str(field)] = errors

    return json.dumps(form_details, indent=4)


def generate_key():
    """Generate a short random and readable key."""

    # letters and numbers without l, 1, i, O, 0, etc.
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    length = settings.URLMAPPING_KEY_LENGTH
    key = "".join(secrets.choice(alphabet) for i in range(length))

    return key


def insert_before(ordered_dict, new_key, new_value, before_key):
    new_dict = OrderedDict()
    for key, value in ordered_dict.items():
        if key == before_key:
            new_dict[new_key] = new_value
        new_dict[key] = value
    return new_dict
