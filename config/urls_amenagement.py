from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from config.urls import handler500  # noqa
from envergo.evaluations.views import ShortUrlAdminRedirectView
from envergo.geodata.views import CatchmentAreaDebug
from envergo.users.views import NewsletterDoubleOptInConfirmation, NewsletterOptIn

from .urls import urlpatterns as common_urlpatterns

# We redefine django auth patterns for better customization
auth_patterns = [
    path(
        _("login/"),
        auth_views.LoginView.as_view(
            template_name="amenagement/registration/login.html"
        ),
        name="login",
    ),
    path(
        _("logout/"),
        auth_views.LogoutView.as_view(
            template_name="amenagement/registration/logged_out.html"
        ),
        name="logout",
    ),
    path(
        _("password_change/"),
        auth_views.PasswordChangeView.as_view(
            form_class=SetPasswordForm,
            template_name="amenagement/registration/password_change_form.html",
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
            template_name="amenagement/registration/password_reset_form.html",
            subject_template_name="amenagement/emails/password_reset_subject.txt",
            email_template_name="amenagement/emails/password_reset.txt",
            html_email_template_name="amenagement/emails/password_reset.html",
            from_email=settings.SITE_FROM_EMAIL["amenagement"],
        ),
        name="password_reset",
    ),
    path(
        _("password_reset/done/"),
        auth_views.PasswordResetDoneView.as_view(
            template_name="amenagement/registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        _("reset/<uidb64>/<token>/"),
        auth_views.PasswordResetConfirmView.as_view(
            template_name="amenagement/registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        _("reset/done/"),
        auth_views.PasswordResetCompleteView.as_view(
            template_name="amenagement/registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]


urlpatterns = [
    path("", include("envergo.pages.urls_amenagement")),
    path(_("accounts/"), include(auth_patterns)),
    path(_("users/"), include("envergo.users.urls")),
    path(
        "a/<slug:reference>/",
        ShortUrlAdminRedirectView.as_view(),
        name="eval_admin_short_url",
    ),
    path("evaluations/", include("envergo.evaluations.redirect_urls")),
    path("évaluations/", include("envergo.evaluations.redirect_urls")),
    path("avis/", include("envergo.evaluations.urls")),
    path(_("moulinette/"), include("envergo.moulinette.urls_amenagement")),
    path(_("geo/"), include("envergo.geodata.urls")),
    path("demonstrateur-bv/", CatchmentAreaDebug.as_view(), name="2150_debug"),
    path("newsletter/", NewsletterOptIn.as_view(), name="newsletter_opt_in"),
    path(
        "newsletter/confirmation/",
        NewsletterDoubleOptInConfirmation.as_view(),
        name="newsletter_confirmation",
    ),
] + common_urlpatterns
