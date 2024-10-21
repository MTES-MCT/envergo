from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from config.urls import handler500  # noqa

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path("", include("envergo.pages.urls_haie")),
    path(_("moulinette/"), include("envergo.moulinette.urls_haie")),
    path("haies/", include("envergo.hedges.urls")),
] + common_urlpatterns
