from django.contrib import admin

from envergo.analytics.models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["category", "event", "session_key", "date_created"]
    search_fields = ["category", "event", "session_key"]
