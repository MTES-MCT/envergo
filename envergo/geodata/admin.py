from django.contrib import admin
from django.contrib.gis import admin as gis_admin

from envergo.geodata.models import Parcel, Zone


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ["commune", "prefix", "section", "order"]
    search_fields = ["commune", "prefix", "section", "order"]


@admin.register(Zone)
class ZoneAdmin(gis_admin.ModelAdmin):
    list_display = ["code"]
