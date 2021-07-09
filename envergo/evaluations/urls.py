from django.urls import path

from envergo.evaluations.views import EvaluationDetail, EvaluationSearch

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        "<slug:application_number>/",
        EvaluationDetail.as_view(),
        name="evaluation_detail",
    ),
]
