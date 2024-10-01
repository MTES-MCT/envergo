from django.urls import path

from envergo.moulinette.views import Triage, TriageResult

from .urls import urlpatterns as common_urlpatterns

urlpatterns = [
    path(
        "",
        Triage.as_view(),
        name="triage",
    ),
    path(
        "exclus",
        TriageResult.as_view(),
        name="triage_result",
    ),
] + common_urlpatterns
