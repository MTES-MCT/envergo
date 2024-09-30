from django.urls import include, path

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path("", include("envergo.pages.urls_haie")),
    path("indre/", include("envergo.moulinette.urls_haie")),
] + common_urlpatterns
