from django.contrib import admin

from envergo.urlmappings.models import UrlMapping


@admin.register(UrlMapping)
class UrlMappingAdmin(admin.ModelAdmin):
    list_display = ("key", "created_at", "url")
    search_fields = ("key", "url")
