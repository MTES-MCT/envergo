from django.contrib.sites.models import Site
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
    site = models.ForeignKey(Site, on_delete=models.CASCADE)

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
        "Accusé de réception demande d’AR, mention délai réponse",
    ),
)

SETTINGS_HELP = {
    "Accusé de réception demande d’AR, mention délai réponse": """
    <p>Paragraphe qui remplace la mention par défaut du délai de traitement des demandes d’avis.</p>
    <p>Utile pour les périodes de vacances.</p>
    <p>Mention par défaut : « Vous recevrez une réponse dans les trois jours ouvrés. »</p>
    <p>(Juste du texte brut, avec éventuels retours à la ligne.)</p>
""",
}


class Setting(models.Model):
    """A single option."""

    setting = models.CharField(
        _("Setting"), max_length=256, choices=SETTINGS, unique=True
    )
    value = models.TextField(_("Value"), max_length=256)

    class Meta:
        verbose_name = _("Setting")
        verbose_name_plural = _("Settings")


class HostedFile(models.Model):
    """A single file."""

    file = models.FileField(_("File"), upload_to="f")
    name = models.CharField(_("Name"), max_length=256)
    description = models.TextField(_("Description"), blank=True)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Hosted file")
        verbose_name_plural = _("Hosted files")

    def __str__(self):
        return self.name
