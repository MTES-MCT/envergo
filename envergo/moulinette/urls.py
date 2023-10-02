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
    path("", MoulinetteHome.as_view(), name="moulinette_home"),
    path(
        _("result/"),
        include(
            [
                path("", MoulinetteResult.as_view(), name="moulinette_result"),
                # We need this url to exist, but it's a "fake" url, it's only
                # used to be logged in matomo, so we can correctry track the funnel
                # moulinette home > missing data > final result
                path(
                    _("missing-data/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_missing_data",
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
