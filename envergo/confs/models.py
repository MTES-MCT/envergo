from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from envergo.utils.markdown import markdown_to_html


class TopBar(models.Model):
    """A singleton object to configure the top bar in admin."""

    message_md = models.TextField(_("Message"))
    message_html = models.TextField(_("Message (html)"), blank=True)
    is_active = models.BooleanField(_("Is active"), default=False)
    updated_at = models.DateTimeField(_("Updated at"), default=timezone.now)

    def __str__(self):
        return "TopBar"

    def save(self, *args, **kwargs):
        self.message_html = markdown_to_html(self.message_md)
        super().save(*args, **kwargs)
