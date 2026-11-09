from django.core.management import BaseCommand
from django.db import transaction

from envergo.security.inventory import read_components
from envergo.security.models import Vulnerability
from envergo.security.osv import find_vulnerabilities


class Command(BaseCommand):
    help = "Update the open vulnerabilities of the libraries the application runs."

    def handle(self, *args, **options):
        """Scan the inventory. An OSV failure raises before the table is touched."""
        components = read_components()
        vulnerabilities_by_component = find_vulnerabilities(components)
        sync_open_vulnerabilities(vulnerabilities_by_component)


@transaction.atomic
def sync_open_vulnerabilities(vulnerabilities_by_component):
    """Make the table match a scan, keeping the detection date of known rows."""
    open_row_pks = []
    for component, vulnerabilities in vulnerabilities_by_component.items():
        for vulnerability in vulnerabilities:
            row, _ = Vulnerability.objects.update_or_create(
                component_name=component.name,
                component_version=component.version,
                ecosystem=component.ecosystem,
                vulnerability_id=vulnerability.id,
                defaults={
                    "summary": vulnerability.summary,
                    "severity": vulnerability.severity,
                    "fixed_versions": vulnerability.fixed_versions,
                },
            )
            open_row_pks.append(row.pk)

    Vulnerability.objects.exclude(pk__in=open_row_pks).delete()
