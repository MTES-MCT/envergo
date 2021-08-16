from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import Evaluation


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    pass


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["application_number", "created_at"]
    form = EvaluationAdminForm

    fieldsets = (
        (None, {"fields": ("application_number",)}),
        (
            _("Project data"),
            {
                "fields": (
                    "commune",
                    "created_surface",
                    "existing_surface",
                )
            },
        ),
        (
            _("Evaluation report"),
            {
                "fields": (
                    "global_probability",
                    "rainwater_runoff_probability",
                    "rainwater_runoff_impact",
                    "flood_zone_probability",
                    "flood_zone_impact",
                    "wetland_probability",
                    "wetland_impact",
                )
            },
        ),
    )
