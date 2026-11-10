from django.contrib import admin

from envergo.security.inventory import UNMONITORED_COMPONENTS, read_components
from envergo.security.models import Vulnerability


@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    """Show the open vulnerabilities as a read-only dashboard, instead of a list."""

    change_list_template = "admin/security/vulnerability/dashboard.html"

    def has_add_permission(self, request):
        """Forbid adding rows: only the scan writes to this table."""
        return False

    def has_change_permission(self, request, obj=None):
        """Forbid editing rows: only the scan writes to this table."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Forbid deleting rows: only the scan writes to this table."""
        return False

    def changelist_view(self, request, extra_context=None):
        """Add the dashboard's data to the admin's list page."""
        rows = Vulnerability.objects.order_by("component_name", "vulnerability_id")
        vulnerabilities = sorted(rows, key=lambda row: row.severity_rank)
        vulnerable_components = {
            vulnerability.component for vulnerability in vulnerabilities
        }
        components = read_components()
        other_components = [c for c in components if c not in vulnerable_components]

        context = {
            **(extra_context or {}),
            "title": "Sécurité des dépendances",
            "vulnerabilities": vulnerabilities,
            "vulnerable_components": vulnerable_components,
            "other_components": other_components,
            "unmonitored_components": UNMONITORED_COMPONENTS,
        }
        return super().changelist_view(request, context)
