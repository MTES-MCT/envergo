from django import forms
from django.contrib import admin
from django import forms

from envergo.analytics.models import CSPReport, Event
from envergo.utils.widgets import JSONWidget


class EventAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "metadata": JSONWidget(attrs={"rows": 20, "cols": 80}),
        }


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["category", "event", "session_key", "date_created", "site"]
    search_fields = ["category", "event", "session_key"]
    form = EventAdminForm


@admin.register(CSPReport)
class CSPReportAdmin(admin.ModelAdmin):
    list_display = ["date_created", "site", "directive_col", "blocked_uri"]

    @admin.display(description="Directive")
    def directive_col(self, obj):
        return obj.content["csp-report"]["violated-directive"]

    @admin.display(description="Uri")
    def blocked_uri(self, obj):
        return obj.content["csp-report"]["blocked-uri"]
