from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from envergo.haies.models import HedgeData


@admin.register(HedgeData)
class HedgeDataAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    ordering = ("created_at",)
    readonly_fields = ["data"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/map/",
                self.admin_site.admin_view(self.hedges_map),
                name="hedges_hedge_map",
            ),
        ]
        return custom_urls + urls

    def hedges_map(self, request, object_id):
        hedge_data = HedgeData.objects.get(id=object_id)
        context = {
            **self.admin_site.each_context(request),
        }

        response = TemplateResponse(request, "haies/hedge_map.html", context)
        return response
