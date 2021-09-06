from django.contrib import admin

from envergo.geodata.models import Parcel


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ["commune", "prefix", "section", "order"]
