from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.moulinette.views import (
    MoulinetteHaieResult,
    MoulinetteResultPlantation,
    Triage,
)

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        "",
        RedirectView.as_view(pattern_name="triage", query_string=True),
        name="moulinette_home",
    ),
    path(
        "triage/",
        Triage.as_view(),
        name="triage",
    ),
    # A fake url for tracking
    path(
        "triage/pre-rempli/",
        RedirectView.as_view(pattern_name="triage"),
        name="moulinette_prefilled_triage",
    ),
    path(
        _("form/"),
        include(
            [
                # This is another "fake" url, only for matomo tracking
                path(
                    "saisie-destruction/",
                    RedirectView.as_view(pattern_name="moulinette_form"),
                    name="moulinette_saisie_d",
                ),
                # This is another "fake" url, only for matomo tracking
                path(
                    "saisie-plantation/",
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_saisie_p",
                ),
            ]
        ),
    ),
    path(
        _("result/"),
        include(
            [
                path("", MoulinetteHaieResult.as_view(), name="moulinette_result"),
            ]
        ),
    ),
    path(
        _("result_p/"),
        include(
            [
                path(
                    "",
                    MoulinetteResultPlantation.as_view(),
                    name="moulinette_result_plantation",
                ),
            ]
        ),
    ),
    path(
        "parametrage/<str:department>/",
        RedirectView.as_view(pattern_name="confighaie_settings", permanent=True),
    ),
] + common_urlpatterns
