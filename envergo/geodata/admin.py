from celery.result import AsyncResult
from django import forms
from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from localflavor.fr.fr_department import DEPARTMENT_CHOICES

from envergo.geodata.forms import DepartmentForm
from envergo.geodata.models import Department, Map, Parcel, Zone
from envergo.geodata.tasks import process_shapefile_map
from envergo.geodata.utils import count_features, extract_shapefile


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ["commune", "prefix", "section", "order"]
    search_fields = ["commune", "prefix", "section", "order"]


class MapForm(forms.ModelForm):
    def clean_file(self):
        """Check that the given file is a valid shapefile archive.

        The official shapefile format is just a bunch of files with
        the same name and different extensions.

        To make things easier, we require to pass those files in a zip archive
        with all the files at the archive root.
        """
        file = self.cleaned_data["file"]
        try:
            with extract_shapefile(file):
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


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    form = MapForm
    list_display = [
        "name",
        "map_type",
        "data_type",
        "departments",
        "display_for_user",
        "expected_zones",
        "import_status",
        "task_status",
    ]
    readonly_fields = [
        "created_at",
        "zone_count",
        "expected_zones",
        "import_status",
        "import_error_msg",
    ]
    actions = ["process"]
    exclude = ["task_id"]
    search_fields = ["name", "display_name"]
    list_filter = ["map_type", "data_type", DepartmentsListFilter]

    def save_model(self, request, obj, form, change):
        obj.expected_zones = count_features(obj.file)
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Extract and import a shapefile"))
    def process(self, request, queryset):
        if queryset.count() > 1:
            error = _("Please only select one map for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        map = queryset[0]
        process_shapefile_map.delay(map.id)
        msg = _(
            "Your shapefile will be processed soon. It might take up to a few minutes."
        )
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


@admin.register(Zone)
class ZoneAdmin(gis_admin.GISModelAdmin):
    list_display = ["id", "map", "created_at", "map_type", "data_type"]
    readonly_fields = ["map", "created_at"]
    list_filter = ["map__map_type", "map__data_type", "map"]

    @admin.display(description=_("Data type"))
    def map_type(self, obj):
        return obj.map.get_map_type_display()

    @admin.display(description=_("Data certainty"))
    def data_type(self, obj):
        return obj.map.get_data_type_display()


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["department"]
    readonly_fields = ["department"]
    fields = ["department"]
    form = DepartmentForm
