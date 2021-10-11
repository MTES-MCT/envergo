from django.urls import path
from django.urls.conf import include
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.views import (
    Dashboard,
    EvaluationDetail,
    EvaluationSearch,
    RequestEvaluation,
    RequestSuccess,
)

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        _("requests/"),
        include(
            [
                path("", RequestEvaluation.as_view(), name="request_evaluation"),
                path(_("success/"), RequestSuccess.as_view(), name="request_success"),
            ]
        ),
    ),
    path(_("dashboard/"), Dashboard.as_view(), name="dashboard"),
    path(
        "<slug:reference>/",
        EvaluationDetail.as_view(),
        name="evaluation_detail",
    ),
]
