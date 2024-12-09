from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.users.views import Register, RegisterSuccess, TokenLogin

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
        _("login/<uidb64>/<token>/"),
        TokenLogin.as_view(template_name="amenagement/registration/login_error.html"),
        name="token_login",
    ),
]
