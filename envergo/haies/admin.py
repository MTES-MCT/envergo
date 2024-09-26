from django.contrib import admin

from envergo.haies.models import HedgeData


@admin.register(HedgeData)
class HedgeDataAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    ordering = ("created_at",)
