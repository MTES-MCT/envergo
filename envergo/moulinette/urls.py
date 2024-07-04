from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.moulinette.views import (
    MoulinetteDebug,
    MoulinetteHome,
    MoulinetteRegulationResult,
    MoulinetteResult,
)

urlpatterns = [
    # Redirections history
    # For a long time, there was no homepage to EnvErgo, so the home url (/) just redirected
    # to the moulinette form (/simulateur), which showed a bit of context about the site.
    # When we designed the home page, the /simulateur url was cleaned and only shows
    # the form.
    # Problem is that many external links or saved urls pointed to the /simulateur/ url,
    # and we feared many people would be lost by discovering EnvErgo throught the form
    # url instead of the real home page. Thus we decided to redirect the /simulateur/ url
    # to the home page.
    path(
        "",
        RedirectView.as_view(pattern_name="home", query_string=True),
        name="moulinette_home_redirect",
    ),
    path(
        _("form/"),
        include(
            [
                path("", MoulinetteHome.as_view(), name="moulinette_home"),
                # We need this url to exist, but it's a "fake" url, it's only
                # used to be logged in matomo, so we can correctry track the funnel
                # moulinette home > missing data > final result
                path(
                    _("missing-data/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_missing_data",
                ),
            ]
        ),
    ),
    path(
        _("result/"),
        include(
            [
                path("", MoulinetteResult.as_view(), name="moulinette_result"),
                # This is another "fake" url, only for matomo tracking
                path(
                    _("debug/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_result_debug",
                ),
                path(
                    "<slug:regulation>/",
                    MoulinetteRegulationResult.as_view(),
                    name="moulinette_criterion_result",
                ),
            ]
        ),
    ),
    path("debug/", MoulinetteDebug.as_view(), name="moulinette_debug"),
]
