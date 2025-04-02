from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from envergo.moulinette.views import MoulinetteAmenagementResult

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        _("result/"),
        include(
            [
                path(
                    "", MoulinetteAmenagementResult.as_view(), name="moulinette_result"
                ),
            ]
        ),
    ),
] + common_urlpatterns
