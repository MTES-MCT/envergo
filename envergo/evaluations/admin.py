from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import linebreaks, mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import (
    Criterion,
    Evaluation,
    Request,
    generate_reference,
)


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    reference = forms.CharField(
        label=_("Reference"),
        help_text=_("If you select an existing request, this value will be replaced."),
        required=False,
        initial=generate_reference,
        max_length=64,
    )
    application_number = forms.CharField(
        label=_("Application number"),
        required=False,
        help_text=_('A 15 chars value starting with "P"'),
        max_length=64,
    )


class CriterionAdminForm(forms.ModelForm):
    pass


class CriterionInline(admin.StackedInline):
    model = Criterion
    fields = ("order", "probability", "criterion", "description_md", "map", "legend_md")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["reference", "application_number", "created_at"]
    form = EvaluationAdminForm
    inlines = [CriterionInline]
    autocomplete_fields = ["request"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reference",
                    "contact_email",
                    "request",
                    "application_number",
                    "evaluation_file",
                )
            },
        ),
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
        (
            _("Contact data"),
            {"fields": ("contact_md",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        """Synchronize the references."""
        if obj.request:
            obj.reference = obj.request.reference
        super().save_model(request, obj, form, change)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "created_at",
        "application_number",
        "contact_email",
        "project_sponsor_phone_number",
    ]
    readonly_fields = ["reference", "created_at", "summary", "parcels", "parcels_map"]
    search_fields = ["reference", "application_number"]
    fieldsets = (
        (None, {"fields": ("reference", "summary")}),
        (_("Project localisation"), {"fields": ("address", "parcels", "parcels_map")}),
        (
            _("Project data"),
            {
                "fields": (
                    "application_number",
                    "created_surface",
                    "existing_surface",
                    "project_description",
                    "additional_data",
                )
            },
        ),
        (
            _("Contact info"),
            {
                "fields": (
                    "contact_email",
                    "project_sponsor_emails",
                    "project_sponsor_phone_number",
                    "send_eval_to_sponsor",
                )
            },
        ),
        (_("Meta info"), {"fields": ("created_at",)}),
    )

    @admin.display(description=_("Lien vers la carte des parcelles"))
    def parcels_map(self, obj):

        parcel_map_url = obj.get_parcel_map_url()
        link = f"<a href='{parcel_map_url}'>Voir la carte</a>"
        return mark_safe(link)

    @admin.display(description=_("Résumé"))
    def summary(self, obj):
        request_url = reverse("admin:evaluations_request_change", args=[obj.reference])
        site = Site.objects.get(id=settings.SITE_ID)

        parcel_map_url = obj.get_parcel_map_url()
        summary_body = render_to_string(
            "evaluations/eval_request_notification.txt",
            {
                "request": obj,
                "request_url": f"https://{site.domain}{request_url}",
                "parcel_map_url": f"https://{site.domain}{parcel_map_url}",
            },
        )
        return mark_safe(linebreaks(summary_body))
