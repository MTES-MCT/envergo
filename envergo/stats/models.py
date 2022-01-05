from django.db import models
from django.utils.translation import gettext_lazy as _


class Stat(models.Model):
    title = models.CharField(_("Title"), max_length=64)
    description = models.TextField(_("Description"))
    order = models.IntegerField(_("Order"), default=100)

    class Meta:
        verbose_name = _("Stat")
        verbose_name_plural = _("Stats")
        ordering = ["order"]
