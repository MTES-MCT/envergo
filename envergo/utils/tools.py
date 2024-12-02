import json
import secrets

from django.conf import settings


def get_base_url(site_domain):
    scheme = "https"
    base_url = f"{scheme}://{site_domain}"
    return base_url


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
