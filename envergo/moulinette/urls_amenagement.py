from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.moulinette.views import MoulinetteAmenagementResult

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        "",
        RedirectView.as_view(pattern_name="moulinette_form", query_string=True),
        name="moulinette_home",
    ),
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
