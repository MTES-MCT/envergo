from django import forms
from django.contrib import admin

from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.petitions.models import InvitationToken, PetitionProject


class InvitationTokenInlineForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_field = self.fields["user"]
        created_by_field = self.fields["created_by"]
        user_field.label_from_instance = lambda user: user.email
        created_by_field.label_from_instance = lambda user: user.email


class InvitationTokenInline(admin.TabularInline):
    model = InvitationToken
    form = InvitationTokenInlineForm
    extra = 0
    verbose_name_plural = "Comptes invités sur le projet"


class DepartmentFilter(admin.SimpleListFilter):
    title = "Département"
    parameter_name = "department"

    def lookups(self, request, model_admin):
        return DEPARTMENT_CHOICES

    def queryset(self, request, queryset):
        # Filter the queryset based on the selected department
        if self.value():
            return queryset.filter(department__department=self.value())
        return queryset


@admin.register(PetitionProject)
class PetitionProjectAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "length_to_remove",
        "length_to_plant",
        "demarches_simplifiees_state",
        "department",
        "created_at",
    )
    inlines = [InvitationTokenInline]
    ordering = ("-created_at",)
    list_filter = [
        "demarches_simplifiees_state",
        DepartmentFilter,
    ]

    def get_queryset(self, request):
        # Use select_related to optimize queries for foreign key fields
        queryset = super().get_queryset(request)
        return queryset.select_related("department", "hedge_data").defer(
            "department__geometry"
        )

    def length_to_plant(self, obj):
        return round(obj.hedge_data.length_to_plant())

    length_to_plant.short_description = "Linéaire à planter"

    def length_to_remove(self, obj):
        return round(obj.hedge_data.length_to_remove())

    length_to_remove.short_description = "Linéaire à détruire"


class InvitationTokenAdminForm(forms.ModelForm):

    class Meta:
        model = InvitationToken
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_field = self.fields["user"]
        created_by_field = self.fields["created_by"]

        user_field.label_from_instance = lambda user: user.email
        created_by_field.label_from_instance = lambda user: user.email


@admin.register(InvitationToken)
class InvitationTokenAdmin(admin.ModelAdmin):

    fields = [
        "token",
        "created_by",
        "petition_project",
        "created_at",
        "user",
        "valid_until",
    ]
    list_display = (
        "id",
        "created_at",
        "created_by_list",
    )
    ordering = ("-created_at",)
    readonly_fields = ("token",)
    form = InvitationTokenAdminForm

    def created_by_list(self, obj):
        created_by = obj.created_by
        return created_by.email if created_by else ""

    created_by_list.short_description = "Compte invitant"
