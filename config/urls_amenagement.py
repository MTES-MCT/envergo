from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from config.urls import handler500  # noqa
from envergo.evaluations.views import ShortUrlAdminRedirectView
from envergo.geodata.views import CatchmentAreaDebug
from envergo.users.views import NewsletterOptIn

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path("", include("envergo.pages.urls_amenagement")),
    path(
        "a/<slug:reference>/",
        ShortUrlAdminRedirectView.as_view(),
        name="eval_admin_short_url",
    ),
    path("evaluations/", include("envergo.evaluations.redirect_urls")),
    path("évaluations/", include("envergo.evaluations.redirect_urls")),
    path("avis/", include("envergo.evaluations.urls")),
    path(_("moulinette/"), include("envergo.moulinette.urls_amenagement")),
    path(_("geo/"), include("envergo.geodata.urls")),
    path("demonstrateur-bv/", CatchmentAreaDebug.as_view(), name="2150_debug"),
    path("newsletter/", NewsletterOptIn.as_view(), name="newsletter_opt_in"),
] + common_urlpatterns
