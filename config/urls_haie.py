from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path("", include("envergo.pages.urls_haie")),
    path(
        "indre/",
        include([path(_("moulinette/"), include("envergo.moulinette.urls"))]),
    ),
] + common_urlpatterns
