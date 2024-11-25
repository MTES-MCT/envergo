from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from envergo.utils.tools import generate_key


class UrlMapping(models.Model):
    """A mapping between a short key and a URL."""

    key = models.CharField(max_length=20, unique=True, default=generate_key)
    url = models.URLField(max_length=2048)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    def __str__(self):
        return f"{self.key}"
