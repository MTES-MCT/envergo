from django.contrib import admin

from envergo.pages.models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ["created_at"]
    search_fields = ["content_md"]
    fields = ["content_md"]
    readonly_fields = ["created_at"]
