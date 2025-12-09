from django.contrib import admin

from envergo.analytics.models import CSPReport, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["category", "event", "session_key", "date_created", "site"]
    search_fields = ["category", "event", "session_key"]


@admin.register(CSPReport)
class CSPReportAdmin(admin.ModelAdmin):
    list_display = ["date_created", "site", "directive_col", "blocked_uri"]

    @admin.display(description="Directive")
    def directive_col(self, obj):
        return obj.content["csp-report"]["violated-directive"]

    @admin.display(description="Uri")
    def blocked_uri(self, obj):
        return obj.content["csp-report"]["blocked-uri"]
