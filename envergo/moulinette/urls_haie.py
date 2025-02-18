from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.moulinette.views import MoulinetteResultPlantation, Triage

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        _("form/"),
        include(
            [
                # This is another "fake" url, only for matomo tracking
                path(
                    "saisie-destruction/",
                    RedirectView.as_view(pattern_name="moulinette_home"),
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
        "",
        Triage.as_view(),
        name="triage",
    ),
] + common_urlpatterns
