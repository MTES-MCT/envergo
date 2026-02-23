from celery.result import AsyncResult
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.gis import admin as gis_admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from localflavor.fr.fr_department import DEPARTMENT_CHOICES

from envergo.geodata.forms import DepartmentForm
from envergo.geodata.models import (
    Department,
    Map,
    RGEAltiDptProcess,
    Zone,
)
from envergo.geodata.tasks import generate_map_preview, process_map
from envergo.geodata.utils import count_features, extract_map



class MapForm(forms.ModelForm):
    def clean_file(self):
        """Check that the given file is a valid map.

        We handle two formats : shapefile and geopackage.

        The official shapefile format is just a bunch of files with
        the same name and different extensions.

        To make things easier, we require to pass those files in a zip archive
        with all the files at the archive root.
        """
        file = self.cleaned_data["file"]
        try:
            with extract_map(file):
                pass  # This file is valid, yeah \o/
        except Exception as e:
            raise ValidationError(_(f"This file does not seem valid ({e})"))
        return file


class DepartmentsListFilter(admin.SimpleListFilter):
    title = _("Departments")
    parameter_name = "departments"
    template = "admin/choice_filter.html"

    def lookups(self, request, model_admin):
        return DEPARTMENT_CHOICES

    def queryset(self, request, queryset):
        lookup_value = self.value()
        if lookup_value:
            queryset = queryset.filter(departments__contains=[lookup_value])
        return queryset


SHORT_MAP_TYPES = {
    "zone_humide": "ZH",
    "zone_inondable": "ZI",
}


@admin.register(Map)
class MapAdmin(gis_admin.GISModelAdmin):
    form = MapForm
    list_display = [
        "name",
        "col_map_type",
        "col_data_type",
        "col_departments",
        "col_display_for_user",
        "col_zones",
        "col_preview_status",
        "col_import_status",
    ]
    readonly_fields = [
        "created_at",
        "zone_count",
        "expected_zones",
        "imported_zones",
        "import_status",
        "import_date",
        "task_status",
        "import_error_msg",
    ]
    actions = ["process", "generate_preview"]
    exclude = ["task_id", "geometry"]
    search_fields = ["name", "display_name"]
    list_filter = ["import_status", "map_type", "data_type", DepartmentsListFilter]
    enable_nav_sidebar = False

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )
        queryset = queryset.defer("geometry")
        return queryset, may_have_duplicates

    def save_model(self, request, obj, form, change):
        obj.expected_zones = count_features(obj.file.file)
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # The `geometry` field can contain huge amount of data
        # Since we don't need it on the list page, we defer it
        qs = qs.defer("geometry").annotate(has_preview=Q(geometry__isnull=False))

        return qs

    def get_deleted_objects(self, objs, request):
        """Get data for the deletion confirmation page.

        We needed to override this, because maps are often associated with
        hundreds of thousands of zones, and the default page was too memory intensive
        and would crash the entire server.
        """
        zone_count = Zone.objects.filter(map__in=objs).count()
        deleted_objects = [str(map) for map in objs]
        deleted_objects.append(f"{zone_count} zones associées")
        model_count = {
            "Cartes": len(objs),
            "Zones": zone_count,
        }
        perms_needed = set()
        protected = {}
        return deleted_objects, model_count, perms_needed, protected

    @admin.display(ordering="map_type", description=_("Type"))
    def col_map_type(self, obj):
        short_map_type = SHORT_MAP_TYPES.get(obj.map_type, obj.get_map_type_display())
        return short_map_type

    @admin.display(
        ordering="data_type",
        description=mark_safe("<abbr title='Valeur carto'>Val.</abbr>"),
    )
    def col_data_type(self, obj):
        return obj.get_data_type_display()

    @admin.display(
        ordering="departments",
        description=mark_safe("<abbr title='Départments'>Depts.</abbr>"),
    )
    def col_departments(self, obj):
        return obj.departments

    @admin.display(
        ordering="display_for_user",
        description=mark_safe(
            "<abbr title='Afficher pour l’utilisateur ?'>Aff.</abbr>"
        ),
        boolean=True,
    )
    def col_display_for_user(self, obj):
        return obj.display_for_user

    @admin.display(
        boolean=True,
        description=mark_safe(
            "<abbr title='Géométrie simplifiée générée ?'>Prévis.</abbr>"
        ),
    )
    def col_preview_status(self, obj):
        return obj.has_preview

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

    @admin.display(
        ordering="imported_zones",
        description=mark_safe(
            "<abbr title='Nb de zones importées / attendues'>Zones</abbr>"
        ),
    )
    def col_zones(self, obj):
        if obj.imported_zones is None:
            imported = "ND"
        else:
            imported = obj.imported_zones

        return f'{imported} / {obj.expected_zones or ""}'

    @admin.action(description=_("Extract and import a map (.shp / gpkg)"))
    def process(self, request, queryset):
        if queryset.count() > 1:
            error = _("Please only select one map for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        map = queryset[0]
        process_map.delay(map.id)
        msg = _("Your map will be processed soon. It might take up to a few minutes.")
        self.message_user(request, msg, level=messages.INFO)

    @admin.action(description=_("Generate the simplified preview geometry"))
    def generate_preview(self, request, queryset):
        if queryset.count() > 1:
            error = _("Please only select one map for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        map = queryset[0]
        generate_map_preview.delay(map.id)
        msg = _("The map preview will be updated soon.")
        self.message_user(request, msg, level=messages.INFO)

    @admin.display(description=_("Extracted zones"))
    def zone_count(self, obj):
        count = Zone.objects.filter(map=obj).count()
        return count

    def task_status(self, obj):
        if not obj.task_id:
            return "ND"

        result = AsyncResult(obj.task_id)
        try:
            status = result.info["msg"]
        except (TypeError, AttributeError, IndexError, KeyError):
            status = "ND"
        return status

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/preview/",
                self.admin_site.admin_view(self.map_preview),
                name="geodata_map_preview",
            ),
        ]
        return custom_urls + urls

    def map_preview(self, request, object_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

        map = self.get_object(request, unquote(object_id))
        context = {
            "map": map,
            "back_url": reverse("admin:geodata_map_change", args=[object_id]),
        }
        response = TemplateResponse(request, "geodata/admin/map_preview.html", context)
        return response


@admin.register(Zone)
class ZoneAdmin(gis_admin.GISModelAdmin):
    list_display = [
        "id",
        "map",
        "created_at",
        "map_type",
        "data_type",
        "area",
        "npoints",
    ]
    readonly_fields = ["map", "created_at", "area", "npoints", "attributes"]
    list_filter = ["map__map_type", "map__data_type"]

    # Prevent an expensive count query
    show_full_result_count = False

    @admin.display(description=_("Data type"))
    def map_type(self, obj):
        return obj.map.get_map_type_display()

    @admin.display(description=_("Data certainty"))
    def data_type(self, obj):
        return obj.map.get_data_type_display()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("map").defer("geometry", "map__geometry")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["department"]
    readonly_fields = ["department"]
    fields = ["department"]
    form = DepartmentForm

    def get_queryset(self, request):
        """Don't load useless and huge geometry objects."""

        qs = super().get_queryset(request)
        qs = qs.defer("geometry")
        return qs

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/preview/",
                self.admin_site.admin_view(self.map_preview),
                name="geodata_department_preview",
            ),
        ]
        return custom_urls + urls

    def map_preview(self, request, object_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

        map = self.get_object(request, unquote(object_id))
        context = {
            "map": map,
            "back_url": reverse("admin:geodata_department_change", args=[object_id]),
        }
        response = TemplateResponse(request, "geodata/admin/map_preview.html", context)
        return response


@admin.register(RGEAltiDptProcess)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ["department", "done", "expected_files", "processed_files"]
