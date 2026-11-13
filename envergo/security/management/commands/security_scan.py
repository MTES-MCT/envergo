from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.urls import reverse

from envergo.security.inventory import read_components
from envergo.security.models import Vulnerability
from envergo.security.osv import find_vulnerabilities
from envergo.utils import tchap
from envergo.utils.tools import get_base_url


class Command(BaseCommand):
    help = "Update the open vulnerabilities of the libraries the application runs."

    def handle(self, *args, **options):
        """Scan the inventory. An OSV failure raises before the table is touched."""
        if not settings.SECURITY_SCAN_ENABLED:
            return

        components = read_components()
        findings_by_component = find_vulnerabilities(components)
        new_vulnerabilities = sync_open_vulnerabilities(findings_by_component)

        urgent_vulnerabilities = [v for v in new_vulnerabilities if v.needs_alert]
        if urgent_vulnerabilities:
            open_count = Vulnerability.objects.count()
            message = build_alert_message(urgent_vulnerabilities, open_count)
            tchap.send(settings.TCHAP_ROOM_ID_SECURITY, message)


@transaction.atomic
def sync_open_vulnerabilities(findings_by_component):
    """Make the table match a scan, keeping the detection date of known rows.

    Returns the rows the scan created, which are the newly found vulnerabilities.
    """
    open_row_pks = []
    new_rows = []
    for component, findings in findings_by_component.items():
        for finding in findings:
            row, created = Vulnerability.objects.update_or_create(
                component_name=component.name,
                component_version=component.version,
                ecosystem=component.ecosystem,
                vulnerability_id=finding.id,
                defaults={
                    "summary": finding.summary,
                    "severity": finding.severity,
                    "fixed_versions": finding.fixed_versions,
                },
            )
            open_row_pks.append(row.pk)
            if created:
                new_rows.append(row)

    Vulnerability.objects.exclude(pk__in=open_row_pks).delete()
    return new_rows


def build_alert_message(urgent_vulnerabilities, open_count):
    """Write the Tchap message announcing urgent new vulnerabilities, worst first."""
    sorted_vulnerabilities = sorted(
        urgent_vulnerabilities, key=lambda vulnerability: vulnerability.severity
    )
    vulnerability_lines = [
        f"- {vulnerability.get_severity_display()} · {vulnerability.component_name} "
        f"{vulnerability.component_version} · "
        f"[{vulnerability.vulnerability_id}]({vulnerability.osv_url})"
        for vulnerability in sorted_vulnerabilities
    ]
    lines = [
        f"Nouvelles vulnérabilités importantes : {len(urgent_vulnerabilities)}",
        *vulnerability_lines,
        f"Vulnérabilités ouvertes au total : {open_count}",
        f"[Tableau de bord]({dashboard_url()})",
    ]
    return "\n".join(lines)


def dashboard_url():
    """Absolute URL of the admin page listing open vulnerabilities."""
    path = reverse(
        "admin:security_vulnerability_changelist", urlconf="config.urls_haie"
    )
    return f"{get_base_url(settings.ENVERGO_HAIE_DOMAIN)}{path}"
