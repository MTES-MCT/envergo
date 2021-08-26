from django.urls import path
from django.urls.conf import include
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.views import (
    EvaluationDetail,
    EvaluationSearch,
    RequestEvaluation,
)

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        _("requests/"),
        include(
            [
                path("", RequestEvaluation.as_view(), name="request_evaluation"),
            ]
        ),
    ),
    path(
        "<slug:application_number>/",
        EvaluationDetail.as_view(),
        name="evaluation_detail",
    ),
]
