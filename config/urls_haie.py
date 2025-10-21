from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from config.urls import handler500  # noqa
from envergo.users.views import ActivateAccount, LoginView, Register, RegisterSuccess

from .urls import urlpatterns as common_urlpatterns

# We redefine django auth patterns for better customization
auth_patterns = [
    path(
        _("login/"),
        LoginView.as_view(
            template_name="haie/registration/login.html", next_page="/projet/liste"
        ),
        name="login",
    ),
    path(
        _("logout/"),
        auth_views.LogoutView.as_view(
            template_name="haie/registration/logged_out.html"
        ),
        name="logout",
    ),
    path(
        _("password_change/"),
        auth_views.PasswordChangeView.as_view(
            form_class=SetPasswordForm,
            template_name="haie/registration/password_change_form.html",
        ),
        name="password_change",
    ),
    path(
        _("password_change/done/"),
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path(
        _("password_reset/"),
        auth_views.PasswordResetView.as_view(
            template_name="haie/registration/password_reset_form.html",
            subject_template_name="haie/emails/password_reset_subject.txt",
            email_template_name="haie/emails/password_reset.txt",
            html_email_template_name="haie/emails/password_reset.html",
            from_email=settings.FROM_EMAIL["haie"]["accounts"],
        ),
        name="password_reset",
    ),
    path(
        _("password_reset/done/"),
        auth_views.PasswordResetDoneView.as_view(
            template_name="haie/registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        _("reset/<uidb64>/<token>/"),
        auth_views.PasswordResetConfirmView.as_view(
            template_name="haie/registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        _("reset/done/"),
        auth_views.PasswordResetCompleteView.as_view(
            template_name="haie/registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        _("register/"),
        Register.as_view(template_name="haie/registration/register.html"),
        name="register",
    ),
    path(
        _("register-success/"),
        RegisterSuccess.as_view(
            template_name="haie/registration/register_success.html"
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
            template_name="haie/registration/activate_account.html"
        ),
        name="activate_account",
    ),
]


urlpatterns = [
    path("", include("envergo.pages.urls_haie")),
    path(_("accounts/"), include(auth_patterns)),
    path(_("moulinette/"), include("envergo.moulinette.urls_haie")),
    path("haies/", include("envergo.hedges.urls")),
    path("projet/", include("envergo.petitions.urls_haie")),
    path("demonstrateurs/", include("envergo.demos.urls")),
] + common_urlpatterns
