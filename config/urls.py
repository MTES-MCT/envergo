from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views import defaults as default_views
from django.views.generic import TemplateView

from envergo.pages.views import server_error
from envergo.urlmappings.views import UrlMappingRedirect

# customize error pages to handle multi-site
handler500 = server_error

# We redefine django auth patterns for better customization
auth_patterns = [
    path(_("login/"), auth_views.LoginView.as_view(), name="login"),
    path(_("logout/"), auth_views.LogoutView.as_view(), name="logout"),
    path(
        _("password_change/"),
        auth_views.PasswordChangeView.as_view(form_class=SetPasswordForm),
        name="password_change",
    ),
    path(
        _("password_change/done/"),
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        _("password_reset/"),
        auth_views.PasswordResetView.as_view(
            subject_template_name="emails/password_reset_subject.txt",
            email_template_name="emails/password_reset.txt",
            html_email_template_name="emails/password_reset.html",
        ),
        name="password_reset",
    ),
    path(
        _("password_reset/done/"),
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        _("reset/<uidb64>/<token>/"),
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        _("reset/done/"),
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]


urlpatterns = [
    path("anymail/", include("anymail.urls")),
    path(_("accounts/"), include(auth_patterns)),
    path(_("users/"), include("envergo.users.urls")),
    path(_("analytics/"), include("envergo.analytics.urls")),
    path(_("feedback/"), include("envergo.analytics.urls")),
    path("urlmappings/", include("envergo.urlmappings.urls")),
    path(
        "simulation/<slug:key>/",
        UrlMappingRedirect.as_view(),
        name="urlmapping_redirect",
    ),
    path(settings.ADMIN_URL, admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns


# Exclude staging envs from search engine results
if settings.ENV_NAME != "production":
    urlpatterns += [
        path(
            "robots.txt",
            TemplateView.as_view(
                template_name="robots_staging.txt", content_type="text/plain"
            ),
        ),
    ]
