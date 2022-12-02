from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from envergo.moulinette.views import (
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
                path(
                    "<slug:regulation>/",
                    MoulinetteRegulationResult.as_view(),
                    name="moulinette_criterion_result",
                ),
            ]
        ),
    ),
]
