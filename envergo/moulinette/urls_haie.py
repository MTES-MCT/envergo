from django.urls import path

from envergo.moulinette.views import Triage

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        "",
        Triage.as_view(),
        name="triage",
    ),
] + common_urlpatterns
