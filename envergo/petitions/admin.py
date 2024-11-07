from django.contrib import admin

from envergo.petitions.models import PetitionProject


@admin.register(PetitionProject)
class PetitionProjectAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "moulinette_url",
        "created_at",
    )
    ordering = ("-created_at",)
