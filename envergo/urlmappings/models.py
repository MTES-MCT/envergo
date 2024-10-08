import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def generate_key():
    """Generate a short random and readable key."""

    # letters and numbers without l, 1, i, O, 0, etc.
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    length = settings.URLMAPPING_KEY_LENGTH
    key = "".join(secrets.choice(alphabet) for i in range(length))

    return key


class UrlMapping(models.Model):
    """A mapping between a short key and a URL."""

    key = models.CharField(max_length=20, unique=True, default=generate_key)
    url = models.URLField(max_length=2048)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    def __str__(self):
        return f"{self.key}"
