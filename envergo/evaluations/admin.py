from django import forms
from django.contrib import admin
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import mark_safe
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

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reference",
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
        "phone_number",
    ]
    readonly_fields = ["reference", "created_at", "parcels", "parcels_map"]
    search_fields = ["reference", "application_number"]
    fieldsets = (
        (None, {"fields": ("reference",)}),
        (_("Project localisation"), {"fields": ("address", "parcels", "parcels_map")}),
        (
            _("Project data"),
            {
                "fields": (
                    "application_number",
                    "created_surface",
                    "existing_surface",
                )
            },
        ),
        (
            _("Contact info"),
            {
                "fields": (
                    "contact_email",
                    "phone_number",
                    "other_contacts",
                )
            },
        ),
        (_("Meta info"), {"fields": ("created_at",)}),
    )

    @admin.display(description=_("Lien vers la carte des parcelles"))
    def parcels_map(self, obj):

        parcel_refs = [parcel.reference for parcel in obj.parcels.all()]
        qd = QueryDict(mutable=True)
        qd.setlist("parcel", parcel_refs)
        map_url = reverse("map")

        link = f"<a href='{map_url}?{qd.urlencode()}'>Voir la carte</a>"
        return mark_safe(link)
