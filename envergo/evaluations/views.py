from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import DetailView, FormView

from envergo.evaluations.forms import EvaluationSearchForm
from envergo.evaluations.models import Criterion, Evaluation


class EvaluationSearch(FormView):
    template_name = "evaluations/search.html"
    form_class = EvaluationSearchForm

    def form_valid(self, form):

        application_number = form.cleaned_data.get("application_number")
        success_url = reverse("evaluation_detail", args=[application_number])
        return HttpResponseRedirect(success_url)


class EvaluationDetail(DetailView):
    template_name = "evaluations/detail.html"
    model = Evaluation
    slug_url_kwarg = "application_number"
    slug_field = "application_number"
    context_object_name = "evaluation"

    def get_queryset(self):
        qs = Evaluation.objects.prefetch_related(
            Prefetch("criterions", queryset=Criterion.objects.order_by("order"))
        )
        return qs

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Http404:
            self.object = None

        context = self.get_context_data(object=self.object)
        if self.object:
            res = self.render_to_response(context)
        else:
            context.update({"application_number": kwargs.get("application_number")})
            res = render(request, "evaluations/not_found.html", context, status=404)

        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["criterions"] = self.object.criterions.all()
        return context
