from django import forms
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from envergo.petitions.models import InvitationToken, PetitionProject
from envergo.users.forms import UserCreationForm
from envergo.utils.fields import NoIdnEmailField

User = get_user_model()


class NoIdnUserCreationForm(UserCreationForm):
    email = NoIdnEmailField(
        required=True,
        label=_("Email address"),
        widget=forms.EmailInput(attrs={"class": "vTextField"}),
    )


class UserForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Let's not fetch the department geometries when displaying the
        # department select widget
        if "departments" in self.fields:
            self.fields["departments"].queryset = self.fields[
                "departments"
            ].queryset.defer("geometry")


class InvitationTokenInline(admin.TabularInline):
    model = InvitationToken
    extra = 0
    fk_name = "user"
    verbose_name_plural = "Droits de consultation"


class FollowedProjectsInline(admin.TabularInline):
    model = PetitionProject.followed_by.through
    extra = 0
    verbose_name_plural = "Projets suivis"
    verbose_name = "Projet suivi"


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):

    add_form = NoIdnUserCreationForm
    form = UserForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("Domains"),
            {"fields": ("access_amenagement", "access_haie")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "departments",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = [
        "email",
        "name",
        "date_joined",
        "is_active",
        "access_amenagement_col",
        "access_haie_col",
        "is_staff_col",
        "superuser_col",
    ]
    readonly_fields = ["last_login", "date_joined"]
    inlines = [InvitationTokenInline, FollowedProjectsInline]
    search_fields = ["name", "email"]
    ordering = ["email"]
    list_filter = [
        "is_active",
        "access_amenagement",
        "access_haie",
        "is_superuser",
        "is_staff",
    ]

    filter_horizontal = (
        "groups",
        "departments",
    )

    @admin.display(
        ordering="is_superuser",
        description="Admin",
        boolean=True,
    )
    def superuser_col(self, obj):
        return obj.is_superuser

    @admin.display(
        ordering="is_staff",
        description="Équipe",
        boolean=True,
    )
    def is_staff_col(self, obj):
        return obj.is_staff

    @admin.display(
        ordering="access_amenagement",
        description="Amgt.",
        boolean=True,
    )
    def access_amenagement_col(self, obj):
        return obj.access_amenagement

    @admin.display(
        ordering="access_haie",
        description="Haie",
        boolean=True,
    )
    def access_haie_col(self, obj):
        return obj.access_haie

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        if db_field.name == "departments":
            qs = kwargs.get("queryset", db_field.remote_field.model.objects)
            # Let's not fetch the department geometries when displaying the
            # department select widget
            kwargs["queryset"] = qs.defer("geometry")
        return super().formfield_for_manytomany(db_field, request=request, **kwargs)
