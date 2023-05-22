from django.contrib import admin

from envergo.pages.models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ["title", "created_at"]
    search_fields = ["title", "content_md"]
    fields = ["title", "content_md", "created_at"]
