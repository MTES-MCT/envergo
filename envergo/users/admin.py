from django import forms
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from envergo.users.forms import UserCreationForm
from envergo.utils.fields import NoIdnEmailField

User = get_user_model()


class NoIdnUserCreationForm(UserCreationForm):
    email = NoIdnEmailField(
        required=True,
        label=_("Email address"),
        widget=forms.EmailInput(attrs={"class": "vTextField"}),
    )


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):

    add_form = NoIdnUserCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
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
    list_display = ["email", "name", "is_superuser", "is_staff"]
    readonly_fields = ["last_login", "date_joined"]
    search_fields = ["name", "email"]
    ordering = ["email"]
