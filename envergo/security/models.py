from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Vulnerability(models.Model):
    """A known flaw currently affecting a library at the version we run."""

    component_name = models.CharField(_("Component"), max_length=255)
    component_version = models.CharField(_("Version"), max_length=64)
    ecosystem = models.CharField(_("Ecosystem"), max_length=32)
    vulnerability_id = models.CharField(_("Identifier"), max_length=64)
    summary = models.TextField(_("Summary"), blank=True)
    severity = models.CharField(_("Severity"), max_length=16)
    fixed_versions = models.JSONField(_("Fixed in"), default=list, blank=True)
    detected_at = models.DateTimeField(_("Detected at"), default=timezone.now)

    class Meta:
        verbose_name = _("Vulnerability")
        verbose_name_plural = _("Vulnerabilities")
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "component_name",
                    "component_version",
                    "ecosystem",
                    "vulnerability_id",
                ],
                name="unique_vulnerability",
            )
        ]

    def __str__(self):
        return (
            f"{self.vulnerability_id} on {self.component_name} {self.component_version}"
        )
