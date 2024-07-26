from django.contrib import admin

from envergo.urlmappings.models import UrlMapping


@admin.site.register(UrlMapping)
class UrlMappingAdmin(admin.ModelAdmin):
    list_display = ("key", "url")
    search_fields = ("key", "url")
