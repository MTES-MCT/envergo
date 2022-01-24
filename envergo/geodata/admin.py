from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Map, Parcel, Zone


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ["commune", "prefix", "section", "order"]
    search_fields = ["commune", "prefix", "section", "order"]


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "zone_count"]
    readonly_fields = ["created_at"]
    actions = ["extract"]

    @admin.action(description=_("Extract and import a shapefile"))
    def extract(self, request, queryset):
        if queryset.count() > 1:
            error = _("Please only select one map for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        map = queryset[0]
        map.extract()

    @admin.display(description=_("Nb zones"))
    def zone_count(self, obj):
        return obj.nb_zones

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(nb_zones=Count("zones"))
        return qs


@admin.register(Zone)
class ZoneAdmin(gis_admin.ModelAdmin):
    list_display = ["id", "map", "created_at"]
