from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.users.views import ActivateAccount, Register, RegisterSuccess

urlpatterns = [
    path(
        _("register/"),
        Register.as_view(template_name="amenagement/registration/register.html"),
        name="register",
    ),
    path(
        _("register-success/"),
        RegisterSuccess.as_view(
            template_name="amenagement/registration/register_success.html"
        ),
        name="register_success",
    ),
    path(
        "enregistrement-succès/",
        RedirectView.as_view(pattern_name="register_success", permanent=True),
    ),
    path(
        _("register/<uidb64>/<token>/"),
        ActivateAccount.as_view(
            template_name="amenagement/registration/activate_account.html"
        ),
        name="activate_account",
    ),
]
