from django.contrib import admin

from envergo.petitions.models import InvitationToken, PetitionProject


class InvitationTokenInline(admin.TabularInline):
    model = InvitationToken
    extra = 0
    verbose_name_plural = "Comptes invités sur le projet"


@admin.register(PetitionProject)
class PetitionProjectAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "length_to_remove",
        "length_to_plant",
        "demarches_simplifiees_state",
        "created_at",
    )
    inlines = [InvitationTokenInline]
    ordering = ("-created_at",)

    def length_to_plant(self, obj):
        return obj.hedge_data.length_to_plant()

    length_to_plant.short_description = "Linéaire à planter"

    def length_to_remove(self, obj):
        return obj.hedge_data.length_to_remove()

    length_to_remove.short_description = "Linéaire à détruire"


admin.site.register(InvitationToken)
