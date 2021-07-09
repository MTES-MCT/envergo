from django.views.generic import DetailView, FormView

from envergo.evaluations.forms import EvaluationSearchForm


class EvaluationSearch(FormView):
    template_name = "evaluations/search.html"
    form_class = EvaluationSearchForm


class EvaluationDetail(DetailView):
    template_name = "evaluations/detail.html"
