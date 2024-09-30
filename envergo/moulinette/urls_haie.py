from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from envergo.moulinette.views import Triage, TriageResult

urlpatterns = [
    path(
        "",
        Triage.as_view(),
        name="triage",
    ),
    path(
        _("result/"),
        TriageResult.as_view(),
        name="triage_result",
    ),
    path(_("moulinette/"), include("envergo.moulinette.urls")),
]
