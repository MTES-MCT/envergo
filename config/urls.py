from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views import defaults as default_views

from envergo.analytics.views import CSPReportView
from envergo.pages.views import rate_limited, server_error
from envergo.urlmappings.views import UrlMappingRedirect

# customize error pages to handle multi-site
handler500 = server_error
handler429 = rate_limited

urlpatterns = [
    path("anymail/", include("anymail.urls")),
    path(_("analytics/"), include("envergo.analytics.urls")),
    path(_("feedback/"), include("envergo.analytics.urls")),
    path("urlmappings/", include("envergo.urlmappings.urls")),
    path(
        "simulation/<slug:key>/",
        UrlMappingRedirect.as_view(),
        name="urlmapping_redirect",
    ),
    path("csp/reports/", CSPReportView.as_view(), name="csp_report"),
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
