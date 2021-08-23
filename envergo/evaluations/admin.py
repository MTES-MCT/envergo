from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import Criterion, Evaluation


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    pass


class CriterionAdminForm(forms.ModelForm):
    pass


class CriterionInline(admin.StackedInline):
    model = Criterion
    fields = ("order", "probability", "criterion", "description_md", "map", "legend")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["application_number", "created_at"]
    form = EvaluationAdminForm
    inlines = [CriterionInline]

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
            {"fields": ("global_probability",)},
        ),
    )
