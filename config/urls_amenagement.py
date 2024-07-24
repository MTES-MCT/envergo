from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.views import ShortUrlAdminRedirectView
from envergo.geodata.views import CatchmentAreaDebug

from .urls import auth_patterns as common_auth_patterns
from .urls import urlpatterns as common_urlpatterns

auth_patterns = common_auth_patterns

urlpatterns = [
    path("", include("envergo.pages.urls")),
    path(
        "a/<slug:reference>/",
        ShortUrlAdminRedirectView.as_view(),
        name="eval_admin_short_url",
    ),
    path("evaluations/", include("envergo.evaluations.redirect_urls")),
    path("évaluations/", include("envergo.evaluations.redirect_urls")),
    path("avis/", include("envergo.evaluations.urls")),
    path(_("moulinette/"), include("envergo.moulinette.urls")),
    path(_("geo/"), include("envergo.geodata.urls")),
    path("demonstrateur-bv/", CatchmentAreaDebug.as_view(), name="2150_debug"),
] + common_urlpatterns