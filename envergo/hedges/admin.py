import json

from django import forms
from django.contrib import admin
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import mark_safe

from envergo.hedges.models import HEDGE_TYPES, HedgeData, Species


@admin.register(HedgeData)
class HedgeDataAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hedges_to_plant",
        "length_to_plant",
        "hedges_to_remove",
        "length_to_remove",
        "created_at",
    )
    ordering = ("-created_at",)
    readonly_fields = [
        "data",
        "hedges",
        "hedges_to_plant",
        "length_to_plant",
        "hedges_to_remove",
        "length_to_remove",
        "all_species",
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/map/",
                self.admin_site.admin_view(self.hedges_map),
                name="hedges_hedgedata_map",
            ),
        ]
        return custom_urls + urls

    def hedges_map(self, request, object_id):
        hedge_data = HedgeData.objects.get(id=object_id)
        back_url = reverse("admin:hedges_hedgedata_change", args=[object_id])
        context = {
            **self.admin_site.each_context(request),
            "hedge_data": json.dumps(hedge_data.data),
            "back_url": back_url,
        }

        response = TemplateResponse(request, "hedges/admin/hedge_map.html", context)
        return response

    def hedges(self, obj):
        content = render_to_string(
            "hedges/admin/_hedges_content.html", context={"hedges": obj.hedges}
        )
        return mark_safe(content)

    def hedges_to_plant(self, obj):
        return len(obj.hedges_to_plant())

    def length_to_plant(self, obj):
        return obj.length_to_plant()

    def hedges_to_remove(self, obj):
        return len(obj.hedges_to_remove())

    def length_to_remove(self, obj):
        return obj.length_to_remove()

    def all_species(self, obj):
        content = render_to_string(
            "hedges/admin/_hedges_species.html",
            context={"species": obj.get_all_species()},
        )
        return mark_safe(content)


class SpeciesAdminForm(forms.ModelForm):
    hedge_types = forms.MultipleChoiceField(
        choices=HEDGE_TYPES,
        widget=forms.CheckboxSelectMultiple,
        label="Types de haies considérés",
        required=False,
    )


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = [
        "common_name",
        "scientific_name",
        "group",
        "hedge_types",
    ]
    ordering = ["-common_name"]
    form = SpeciesAdminForm
    list_filter = ["group"]
