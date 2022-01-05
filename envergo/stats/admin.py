from django.contrib import admin

from envergo.stats.models import Stat


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ["title", "description", "order"]
    list_editable = ["order"]
