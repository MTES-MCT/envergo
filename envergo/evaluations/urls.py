from django.urls import path

from envergo.evaluations.views import EvaluationDetail, EvaluationSearch

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path("<uuid:uid>/", EvaluationDetail.as_view(), name="evaluation_detail"),
]
