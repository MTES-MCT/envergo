import json

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path, reverse

from envergo.hedges.models import HedgeData


@admin.register(HedgeData)
class HedgeDataAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hedges_to_plant",
        "length_to_plant",
        "hedges_to_remove",
        "length_to_remove",
        "created_at",
    )
    ordering = ("-created_at",)
    readonly_fields = [
        "data",
        "hedges_to_plant",
        "length_to_plant",
        "hedges_to_remove",
        "length_to_remove",
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/map/",
                self.admin_site.admin_view(self.hedges_map),
                name="hedges_hedgedata_map",
            ),
        ]
        return custom_urls + urls

    def hedges_map(self, request, object_id):
        hedge_data = HedgeData.objects.get(id=object_id)
        back_url = reverse("admin:hedges_hedgedata_change", args=[object_id])
        context = {
            **self.admin_site.each_context(request),
            "hedge_data": json.dumps(hedge_data.data),
            "back_url": back_url,
        }

        response = TemplateResponse(request, "hedges/admin/hedge_map.html", context)
        return response

    def hedges_to_plant(self, obj):
        return len(obj.hedges_to_plant())

    def length_to_plant(self, obj):
        return sum(h.length for h in obj.hedges_to_plant())

    def hedges_to_remove(self, obj):
        return len(obj.hedges_to_remove())

    def length_to_remove(self, obj):
        return sum(h.length for h in obj.hedges_to_remove())
