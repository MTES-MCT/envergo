from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def make_activate_account_url(user):
    """Create a one-time login url for some user."""

    user_uid = urlsafe_base64_encode(force_bytes(user.pk))
    login_token = default_token_generator.make_token(user)
    login_url = reverse("activate_account", args=[user_uid, login_token])

    return login_url
