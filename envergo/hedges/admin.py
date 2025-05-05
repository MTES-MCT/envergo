import json

from celery.result import AsyncResult
from django import forms
from django.contrib import admin, messages
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import mark_safe

from envergo.hedges.models import (
    HEDGE_PROPERTIES,
    HEDGE_TYPES,
    HedgeData,
    Species,
    SpeciesMap,
    SpeciesMapFile,
)
from envergo.hedges.tasks import process_species_map_file


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

    @admin.display(description="Nombre de haies à planter")
    def hedges_to_plant(self, obj):
        return len(obj.hedges_to_plant())

    @admin.display(description="Longueur des haies à planter")
    def length_to_plant(self, obj):
        return round(obj.length_to_plant())

    @admin.display(description="Nombre de haies à détruire")
    def hedges_to_remove(self, obj):
        return len(obj.hedges_to_remove())

    @admin.display(description="Longueur des haies à détruire")
    def length_to_remove(self, obj):
        return round(obj.length_to_remove())

    def all_species(self, obj):
        """Display list of protected species related to this hedge set."""

        content = render_to_string(
            "hedges/admin/_hedges_species.html",
            context={"species": obj.get_all_species()},
        )
        return mark_safe(content)


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = [
        "common_name",
        "scientific_name",
        "group",
        "level_of_concern",
        "highly_sensitive",
        "taxref_ids",
    ]
    search_fields = ["group", "common_name", "scientific_name"]
    ordering = ["-common_name"]
    list_filter = ["group", "level_of_concern", "highly_sensitive"]
    readonly_fields = ["kingdom", "taxref_ids"]


class SpeciesMapAdminForm(forms.ModelForm):
    hedge_types = forms.MultipleChoiceField(
        choices=HEDGE_TYPES,
        widget=forms.CheckboxSelectMultiple,
        label="Types de haies considérés",
        required=False,
    )
    hedge_properties = forms.MultipleChoiceField(
        choices=HEDGE_PROPERTIES,
        widget=forms.CheckboxSelectMultiple,
        label="Caractéristiques de haies concernées",
        required=False,
    )


@admin.register(SpeciesMap)
class SpeciesMapAdmin(admin.ModelAdmin):
    form = SpeciesMapAdminForm
    list_display = [
        "species",
        "map",
        "hedge_types",
        "hedge_properties",
    ]
    autocomplete_fields = ["species", "map"]


@admin.register(SpeciesMapFile)
class SpeciesMapFileAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "file",
        "map",
        "col_import_status",
    ]
    readonly_fields = [
        "created_at",
        "import_status",
        "import_date",
        "task_status",
        "import_log",
    ]
    ordering = ["-id"]
    search_fields = ["name"]
    autocomplete_fields = ["map"]
    actions = ["process"]
    exclude = ["task_id", "geometry"]

    @admin.display(
        ordering="import_status",
        description=mark_safe("<abbr title='Importé avec succes ?'>Imp.</abbr>"),
    )
    def col_import_status(self, obj):
        if not obj.import_status:
            return ""

        icons = {
            "success": "/static/admin/img/icon-yes.svg",
            "failure": "/static/admin/img/icon-no.svg",
            "partial_success": "/static/admin/img/icon-alert.svg",
        }
        icon = icons.get(obj.import_status)
        html = f"<img src='{icon}' title='{obj.get_import_status_display()}' alt='{obj.get_import_status_display()}'/>"
        return mark_safe(html)

    def task_status(self, obj):
        if not obj.task_id:
            return "ND"

        result = AsyncResult(obj.task_id)
        try:
            status = result.info["msg"]
        except (TypeError, AttributeError, IndexError, KeyError):
            status = "ND"
        return status

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("map").defer("map__geometry")

    @admin.action(description="Importer la carte d'espèces")
    def process(self, request, queryset):
        if queryset.count() > 1:
            error = "Merci de ne sélectionner qu'une seule carte"
            self.message_user(request, error, level=messages.ERROR)
            return

        map = queryset[0]
        process_species_map_file.delay(map.id)
        msg = "Votre fichier est en cours de traitement."
        self.message_user(request, msg, level=messages.INFO)
