from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.moulinette.views import MoulinetteForm

urlpatterns = [
    # This is another "fake" url, only for matomo tracking
    path(
        _("out_of_scope/"),
        RedirectView.as_view(pattern_name="moulinette_result"),
        name="moulinette_result_out_of_scope",
    ),
    path(
        _("form/"),
        include(
            [
                path("", MoulinetteForm.as_view(), name="moulinette_form"),
                # We need this url to exist, but it's a "fake" url, it's only
                # used to be logged in matomo, so we can correctry track the funnel
                # moulinette home > missing data > final result
                path(
                    _("missing-data/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_missing_data",
                ),
                # This is another "fake" url, only for matomo tracking
                path(
                    _("invalid/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_invalid_form",
                ),
                # An another one
                path(
                    "pre-rempli/",
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_prefilled_form",
                ),
            ]
        ),
    ),
    path(
        _("result/"),
        include(
            [
                # This is another "fake" url, only for matomo tracking
                path(
                    _("debug/"),
                    RedirectView.as_view(pattern_name="moulinette_result"),
                    name="moulinette_result_debug",
                ),
            ]
        ),
    ),
]
