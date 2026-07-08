import json
import logging

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.petitions.demarche_numerique.client import DemarcheNumeriqueError
from envergo.petitions.models import (
    InvitationToken,
    PetitionProject,
    ResultSnapshot,
    Simulation,
)
from envergo.petitions.services import get_demarche_numerique_dossier
from envergo.users.models import User
from envergo.utils.validators import validate_mime
from envergo.utils.widgets import JSONWidget

logger = logging.getLogger(__name__)


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


def validate_zip(value):
    validate_mime(value, ["application/zip"])


def validate_dn_file_size(value):
    size_limit = settings.DEMARCHE_NUMERIQUE["ARCHIVE_MAX_SIZE"]
    if value.size > size_limit:
        raise ValidationError(
            "Le fichier excède la taille maximale autorisée de 20 Mo."
        )


class PetitionProjectAdminForm(forms.ModelForm):
    followed_by = UserMultipleChoiceField(
        label="Instructeurs suivant le projet",
        queryset=User.objects.all().order_by("email"),
        widget=FilteredSelectMultiple(_("Users"), is_stacked=False),
        required=False,
    )

    dn_archive = forms.FileField(
        label="Archive Démarche Numérique",
        required=False,
        help_text="""Format autorisé: zip.<br>
        Taille maximale autorisée : 20 Mo.
        """,
        validators=[validate_zip, validate_dn_file_size],
    )

    class Meta:
        model = PetitionProject
        fields = "__all__"
        widgets = {
            "demarche_numerique_raw_dossier": JSONWidget(
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
        "demarche_numerique_state",
        "length_to_remove",
        "length_to_plant",
    )
    inlines = [InvitationTokenInline]
    ordering = ("-created_at",)
    list_filter = [
        "demarche_numerique_state",
        DepartmentFilter,
    ]
    readonly_fields = ["last_result_snapshot"]

    def get_queryset(self, request):
        # Use select_related to optimize queries for foreign key fields
        queryset = super().get_queryset(request)
        return queryset.select_related("department", "hedge_data").defer(
            "department__geometry"
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # A manually attached dossier is never picked up by the hourly sync
        # command (its `updatedSince` filter excludes dossiers not recently
        # updated on the DN side), so we force a sync right away.
        if (
            "demarche_numerique_dossier_number" in form.changed_data
            and obj.demarche_numerique_dossier_number
        ):
            dossier_number = obj.demarche_numerique_dossier_number
            try:
                dossier = get_demarche_numerique_dossier(obj, force_update=True)
            except DemarcheNumeriqueError:
                logger.exception(
                    "Unable to synchronize petition project %s with dossier %s",
                    obj.reference,
                    dossier_number,
                )
                self.message_user(
                    request,
                    f"La synchronisation avec Démarche Numérique a échoué pour le "
                    f"dossier n°{dossier_number}. Le projet a bien été enregistré.",
                    messages.ERROR,
                )
            else:
                if dossier:
                    self.message_user(
                        request,
                        f"Le dossier Démarche Numérique n°{dossier_number} a été "
                        f"synchronisé avec le projet.",
                        messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"Aucun dossier Démarche Numérique trouvé pour le "
                        f"n°{dossier_number} — vérifiez le numéro.",
                        messages.WARNING,
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
            <summary>Déployer</summary>
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
        "petition_project",
        "user_list",
        "token",
    )
    search_fields = ["token"]
    ordering = ("-created_at",)
    readonly_fields = ("token",)
    form = InvitationTokenAdminForm

    def created_by_list(self, obj):
        created_by = obj.created_by
        return created_by.email if created_by else ""

    def user_list(self, obj):
        user = obj.user
        return user.email if user else ""

    created_by_list.short_description = "Compte invitant"
    user_list.short_description = "Compte invité"


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ["project", "is_initial", "is_active", "source", "created_at"]
    search_fields = ["project__reference"]
