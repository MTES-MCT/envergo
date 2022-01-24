from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Map, Parcel, Zone


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ["commune", "prefix", "section", "order"]
    search_fields = ["commune", "prefix", "section", "order"]


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
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


@admin.register(Zone)
class ZoneAdmin(gis_admin.ModelAdmin):
    list_display = ["created_at"]
