import json

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.petitions.models import (
    InvitationToken,
    PetitionProject,
    ResultSnapshot,
    Simulation,
)
from envergo.users.models import User
from envergo.utils.widgets import JSONWidget


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


class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.email


class PetitionProjectAdminForm(forms.ModelForm):
    followed_by = UserMultipleChoiceField(
        label="Instructeurs suivant le projet",
        queryset=User.objects.all().order_by("email"),
        widget=FilteredSelectMultiple(_("Users"), is_stacked=False),
        required=False,
    )

    class Meta:
        model = PetitionProject
        fields = "__all__"
        widgets = {
            "demarches_simplifiees_raw_dossier": JSONWidget(
                attrs={"rows": 20, "cols": 80}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["followed_by"].widget.can_add_related = False


@admin.register(PetitionProject)
class PetitionProjectAdmin(admin.ModelAdmin):
    form = PetitionProjectAdminForm
    list_display = (
        "reference",
        "created_at",
        "department",
        "demarches_simplifiees_state",
        "length_to_remove",
        "length_to_plant",
    )
    inlines = [InvitationTokenInline]
    ordering = ("-created_at",)
    list_filter = [
        "demarches_simplifiees_state",
        DepartmentFilter,
    ]
    readonly_fields = ["last_result_snapshot"]

    def get_queryset(self, request):
        # Use select_related to optimize queries for foreign key fields
        queryset = super().get_queryset(request)
        return queryset.select_related("department", "hedge_data").defer(
            "department__geometry"
        )

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))

        fields.remove("last_result_snapshot")

        if obj:
            index = fields.index("hedge_data") + 1
            fields.insert(index, "last_result_snapshot")

        return fields

    def length_to_plant(self, obj):
        return round(obj.hedge_data.length_to_plant())

    length_to_plant.short_description = "Linéaire à planter"

    def length_to_remove(self, obj):
        return round(obj.hedge_data.length_to_remove())

    length_to_remove.short_description = "Linéaire à détruire"

    @admin.display(description="Dernier résultat de simulation")
    def last_result_snapshot(self, obj):
        snapshot = (
            ResultSnapshot.objects.filter(project=obj).order_by("-created_at").first()
        )
        if not snapshot:
            return "—"

        # Pretty JSON
        pretty = json.dumps(snapshot.payload, indent=2, ensure_ascii=False)
        return format_html(
            """
        <details>
            <summary>Afficher le JSON</summary>
            <pre>{}</pre>
        </details>
    """,
            pretty,
        )


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


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ["project", "is_initial", "is_active", "source", "created_at"]
    search_fields = ["project__reference"]
