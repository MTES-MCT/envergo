from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from envergo.security.inventory import Component, Ecosystem

# An unrated flaw ranks above moderate ones: having no rating does not make it minor.
SEVERITY_RANKS = {
    "malicious": 0,
    "critical": 1,
    "high": 2,
    "unknown": 3,
    "moderate": 4,
    "low": 5,
}

# A new vulnerability this severe or worse alerts the security Tchap room.
ALERT_SEVERITY_RANK = SEVERITY_RANKS["high"]


# Days a vulnerability can stay open before its age tag escalates.
OPEN_DAYS_AGING = 3
OPEN_DAYS_OVERDUE = 7


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

    @property
    def severity_rank(self):
        """Return the position in the dashboard: lower means more urgent."""
        return SEVERITY_RANKS.get(self.severity, SEVERITY_RANKS["unknown"])

    @property
    def needs_alert(self):
        """Tell whether this vulnerability, once found, calls for immediate action."""
        return self.severity_rank <= ALERT_SEVERITY_RANK

    @property
    def open_days(self):
        """Return how many full days have passed since the first detection."""
        return (timezone.now() - self.detected_at).days

    @property
    def open_age(self):
        """Return how late the fix is: "recent", "aging" or "overdue"."""
        if self.open_days > OPEN_DAYS_OVERDUE:
            age = "overdue"
        elif self.open_days >= OPEN_DAYS_AGING:
            age = "aging"
        else:
            age = "recent"
        return age

    @property
    def osv_url(self):
        """Return the address of this vulnerability's page on OSV.dev."""
        return f"https://osv.dev/vulnerability/{self.vulnerability_id}"

    @property
    def component(self):
        """Return the library this vulnerability affects."""
        ecosystem = Ecosystem(self.ecosystem)
        return Component(self.component_name, self.component_version, ecosystem)

    def __str__(self):
        return (
            f"{self.vulnerability_id} on {self.component_name} {self.component_version}"
        )
