import logging
from os.path import splitext

from celery.result import AsyncResult
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.gis import admin as gis_admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile, UploadedFile
from django.db.models import Q
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from localflavor.fr.fr_department import DEPARTMENT_CHOICES

from envergo.geodata.forms import DepartmentForm
from envergo.geodata.models import (
    Department,
    Line,
    Map,
    MapImportBatch,
    MapImportBatchFile,
    Zone,
)
from envergo.geodata.tasks import (
    generate_map_preview,
    process_map,
    process_map_import_batch,
)
from envergo.geodata.utils import count_features, extract_map
from envergo.utils.validators import detect_mime, validate_mime

# Libmagic reports csv files as plain text, and only recognizes the `text/csv`
# structure on files with enough rows to sniff a consistent separator.
CSV_MIME_TYPES = {"text/csv", "text/plain", "application/csv"}

# A geopackage is a sqlite database; the exact label depends on the libmagic
# version. The extension drives how `extract_map` reads the file, so each
# extension is checked against the content types it is allowed to hold.
BATCH_FILE_MIME_TYPES = {
    ".gpkg": {
        "application/vnd.sqlite3",
        "application/x-sqlite3",
        "application/geopackage+sqlite3",
    },
    ".zip": {"application/zip", "application/x-zip-compressed"},
}

logger = logging.getLogger(__name__)


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
        "reference",
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
        "expected_geometries",
        "imported_geometries",
        "import_status",
        "import_date",
        "task_status",
        "import_error_msg",
        "import_batch_link",
        "batch_created_at",
        "batch_updated_at",
    ]
    actions = ["process", "generate_preview"]
    exclude = ["task_id", "geometry", "import_batch"]
    search_fields = ["name", "display_name", "reference"]
    list_filter = ["import_status", "map_type", "data_type", DepartmentsListFilter]
    enable_nav_sidebar = False

    def lookup_allowed(self, lookup, value, *args, **kwargs):
        # The batch admin page links to the list of maps it created,
        # without needing a `list_filter` entry.
        if lookup == "import_batch__id__exact":
            return True
        return super().lookup_allowed(lookup, value, *args, **kwargs)

    @admin.display(description="Importé par lot")
    def import_batch_link(self, obj):
        if not obj.import_batch:
            return "ND"
        url = reverse("admin:geodata_mapimportbatch_change", args=[obj.import_batch.pk])
        return format_html('<a href="{}">{}</a>', url, obj.import_batch)

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )
        queryset = queryset.defer("geometry")
        return queryset, may_have_duplicates

    def save_model(self, request, obj, form, change):
        # Django's DataSource seems to only be able to open local files
        # So we only can (and need) to extract the file to count the expected features
        # if a new file is uploaded and is currently being processed on the server
        if isinstance(obj.file.file, TemporaryUploadedFile):
            obj.expected_geometries = count_features(obj.file.file)
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
        line_count = Line.objects.filter(map__in=objs).count()
        deleted_objects = [str(map) for map in objs]
        deleted_objects.append(f"{zone_count} zones associées")
        deleted_objects.append(f"{line_count} lignes associées")
        model_count = {
            "Cartes": len(objs),
            "Zones": zone_count,
            "Lignes": line_count,
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
        ordering="imported_geometries",
        description=mark_safe(
            "<abbr title='Nb de zones importées / attendues'>Zones</abbr>"
        ),
    )
    def col_zones(self, obj):
        if obj.imported_geometries is None:
            imported = "ND"
        else:
            imported = obj.imported_geometries

        return f'{imported} / {obj.expected_geometries or ""}'

    @admin.action(description=_("Extract and import a map (.shp / gpkg)"))
    def process(self, request, queryset):

        for map in queryset:
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


class MapImportBatchForm(forms.ModelForm):
    def clean_csv_file(self):
        file = self.cleaned_data["csv_file"]

        # On a change form with an untouched file, the value is the stored
        # FieldFile: there is nothing new to check, and sniffing it would
        # mean downloading it back from the bucket.
        if not isinstance(file, UploadedFile):
            return file

        if not file.name.lower().endswith(".csv"):
            raise ValidationError("Ce fichier doit être un fichier csv.")

        # The extension is declarative; check the actual bytes too.
        validate_mime(file, CSV_MIME_TYPES)
        return file


@admin.register(MapImportBatch)
class MapImportBatchAdmin(admin.ModelAdmin):
    form = MapImportBatchForm
    list_display = [
        "name",
        "created_at",
        "created_by",
        "col_file_count",
        "col_import_status",
    ]
    readonly_fields = [
        "created_at",
        "created_by",
        "import_status",
        "import_date",
        "task_status",
        "import_log",
        "upload_link",
        "maps_link",
    ]
    exclude = ["task_id"]
    actions = ["process"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Fichiers téléversés")
    def col_file_count(self, obj):
        return obj.files.count()

    @admin.display(
        ordering="import_status",
        description=mark_safe("<abbr title='Importé avec succes ?'>Imp.</abbr>"),
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

    @admin.display(description="Fichiers de cartes")
    def upload_link(self, obj):
        if not obj.pk:
            return "Enregistrez d'abord le lot pour téléverser les fichiers."
        url = reverse("admin:geodata_mapimportbatch_upload", args=[obj.pk])
        return format_html('<a href="{}">Téléverser les fichiers</a>', url)

    @admin.display(description="Cartes du lot")
    def maps_link(self, obj):
        if not obj.pk:
            return "ND"
        url = reverse("admin:geodata_map_changelist")
        return format_html(
            '<a href="{}?import_batch__id__exact={}">Voir les cartes du lot ({})</a>',
            url,
            obj.pk,
            obj.maps.count(),
        )

    @admin.action(description="Traiter les lots (création / màj des cartes)")
    def process(self, request, queryset):
        queued = 0
        for batch in queryset:
            process_map_import_batch.delay(batch.id)
            queued += 1

        if queued:
            self.message_user(
                request,
                f"{queued} lot(s) en cours de traitement. "
                f"Cela peut prendre plusieurs minutes.",
                level=messages.INFO,
            )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/upload/",
                self.admin_site.admin_view(self.upload_view),
                name="geodata_mapimportbatch_upload",
            ),
        ]
        return custom_urls + urls

    def upload_view(self, request, object_id):
        """Handle the multi-file upload page (dropzone)."""

        if not self.has_change_permission(request):
            raise PermissionDenied

        batch = self.get_object(request, unquote(object_id))
        if batch is None:
            return JsonResponse({"error": "Ce lot n'existe pas."}, status=404)

        if request.method == "POST":
            return self.handle_upload(request, batch)
        elif request.method == "DELETE":
            return self.handle_delete(request, batch)

        uploaded_files = []
        for batch_file in batch.files.all():
            try:
                size = batch_file.file.size
            except FileNotFoundError:
                size = 0
            uploaded_files.append(
                {"id": batch_file.id, "name": batch_file.name, "size": size}
            )

        context = {
            **self.admin_site.each_context(request),
            "batch": batch,
            "opts": self.opts,
            "uploaded_files": uploaded_files,
            "max_files": settings.MAX_MAP_BATCH_FILES,
            "max_filesize": settings.MAX_MAP_BATCH_FILESIZE,
            "upload_url": reverse(
                "admin:geodata_mapimportbatch_upload", args=[batch.pk]
            ),
            "back_url": reverse("admin:geodata_mapimportbatch_change", args=[batch.pk]),
        }
        return TemplateResponse(
            request, "geodata/admin/mapimportbatch_upload.html", context
        )

    def handle_upload(self, request, batch):
        """This is called when a file is uploaded with dropzone."""

        max_files = settings.MAX_MAP_BATCH_FILES
        if batch.files.count() >= max_files:
            return JsonResponse(
                {"error": f"Vous ne pouvez pas envoyer plus de {max_files} fichiers."},
                status=400,
            )

        file = request.FILES.get("map_files")
        if not file:
            return JsonResponse({"error": "Aucun fichier n'a été reçu."}, status=400)

        max_size_bytes = settings.MAX_MAP_BATCH_FILESIZE * 1024 * 1024
        if file.size > max_size_bytes:
            return JsonResponse(
                {
                    "error": f"Ce fichier est trop volumineux. "
                    f"Maximum : {settings.MAX_MAP_BATCH_FILESIZE} Mo."
                },
                status=400,
            )

        _, extension = splitext(file.name.lower())
        allowed_mime_types = BATCH_FILE_MIME_TYPES.get(extension)
        if allowed_mime_types is None:
            return JsonResponse(
                {
                    "error": "Ce type de fichier n'est pas autorisé "
                    "(.gpkg ou .zip attendu)."
                },
                status=400,
            )

        # The extension is declarative; check the actual bytes too.
        detected = detect_mime(file)
        if detected not in allowed_mime_types:
            logger.warning(
                f"Fichier de lot rejeté : {file.name} a un type MIME détecté "
                f"de {detected}, incompatible avec l'extension {extension}."
            )
            return JsonResponse(
                {
                    "error": f"Le contenu de ce fichier ne correspond pas à un "
                    f"fichier {extension}."
                },
                status=400,
            )

        if batch.files.filter(name=file.name).exists():
            return JsonResponse(
                {"error": f"Le fichier {file.name} a déjà été téléversé."},
                status=400,
            )

        batch_file = MapImportBatchFile.objects.create(
            batch=batch,
            file=file,
            name=file.name,
        )
        return JsonResponse({"id": batch_file.id})

    def handle_delete(self, request, batch):
        """This is called when a file is removed with dropzone."""

        try:
            file_id = request.GET.get("file_id")
            batch_file = batch.files.get(id=file_id)
            batch_file.file.delete(save=False)
            batch_file.delete()
            return JsonResponse({})
        except MapImportBatchFile.DoesNotExist:
            return JsonResponse({"error": "Ce fichier n'existe pas."}, status=400)


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
    readonly_fields = [
        "map",
        "created_at",
        "area",
        "npoints",
        "attributes",
        "species_taxrefs",
    ]
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


@admin.register(Line)
class LineAdmin(gis_admin.GISModelAdmin):
    list_display = [
        "id",
        "map",
        "created_at",
        "map_type",
        "data_type",
    ]
    readonly_fields = ["map", "created_at", "attributes"]
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
