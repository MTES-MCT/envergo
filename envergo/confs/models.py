from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.utils.markdown import markdown_to_html


class TopBar(models.Model):
    """An object to configure the main message top bars."""

    message_md = models.TextField(_("Message"))
    message_html = models.TextField(_("Message (html)"), blank=True)
    is_active = models.BooleanField(_("Is active"), default=False)
    updated_at = models.DateTimeField(_("Updated at"), default=timezone.now)

    def __str__(self):
        return "TopBar"

    def save(self, *args, **kwargs):
        paragraph = markdown_to_html(self.message_md)
        striped = paragraph.removeprefix("<p>").removesuffix("</p>")
        self.message_html = striped
        super().save(*args, **kwargs)


SETTINGS = Choices(
    (
        "evalreq_confirmation_email_delay_mention",
        "E-mail de confirmation de demande d'éval., mention de la délai de réponse",
    ),
)


class Setting(models.Model):
    """A single option."""

    setting = models.CharField(
        _("Setting"), max_length=256, choices=SETTINGS, unique=True
    )
    value = models.TextField(_("Value"), max_length=256)

    class Meta:
        verbose_name = _("Setting")
        verbose_name_plural = _("Settings")
