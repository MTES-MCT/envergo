from django import forms
from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

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


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    form = MapForm
    list_display = [
        "name",
        "data_type",
        "created_at",
        "expected_zones",
        "zone_count",
        "import_status",
    ]
    readonly_fields = [
        "created_at",
        "expected_zones",
        "import_status",
        "import_error_msg",
    ]
    actions = ["process"]
    exclude = ["task_id"]

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

    @admin.display(description=_("Nb zones"))
    def zone_count(self, obj):
        return obj.nb_zones

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(nb_zones=Count("zones"))
        return qs


@admin.register(Zone)
class ZoneAdmin(gis_admin.OSMGeoAdmin):
    list_display = ["id", "map", "created_at"]
    readonly_fields = ["map", "created_at"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["department"]
    readonly_fields = ["department"]
    fields = ["department", "contact_md"]
    form = DepartmentForm
