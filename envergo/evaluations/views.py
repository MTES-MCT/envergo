from django.db import transaction
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from django.views.generic.edit import CreateView

from envergo.evaluations.forms import EvaluationSearchForm, RequestForm
from envergo.evaluations.models import Criterion, Evaluation
from envergo.geodata.forms import ParcelFormSet, ParcelMapForm


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

        if self.object:
            context["criterions"] = self.object.criterions.all()
        return context


class RequestEvaluation(CreateView):
    template_name = "evaluations/request.html"
    form_class = RequestForm

    def get_parcel_formset(self):
        form_kwargs = self.get_form_kwargs()
        form_kwargs["prefix"] = "parcel"

        if "instance" in form_kwargs:
            del form_kwargs["instance"]

        parcel_formset = ParcelFormSet(**form_kwargs)
        return parcel_formset

    def get_context_data(self, **kwargs):
        if "parcel_formset" not in kwargs:
            kwargs["parcel_formset"] = self.get_parcel_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        self.object = None
        form = self.get_form()
        parcel_formset = self.get_parcel_formset()
        if form.is_valid() and parcel_formset.is_valid():
            return self.form_valid(form, parcel_formset)
        else:
            return self.form_invalid(form, parcel_formset)

    def form_valid(self, form, parcel_formset):
        with transaction.atomic():
            evaluation = form.save()
            parcels = parcel_formset.save()
            evaluation.parcels.set(parcels)

        success_url = reverse("request_success")
        return HttpResponseRedirect(success_url)

    def form_invalid(self, form, parcel_formset):
        return self.render_to_response(
            self.get_context_data(
                form=form,
                parcel_formset=parcel_formset,
                other_form_errors=parcel_formset.errors,
            )
        )


class RequestSuccess(TemplateView):
    template_name = "evaluations/request_success.html"


class MapTest(FormView):
    template_name = "evaluations/map_test.html"
    form_class = ParcelMapForm

    def get_parcel_formset(self):
        form_kwargs = self.get_form_kwargs()
        form_kwargs["prefix"] = "parcel"

        if "instance" in form_kwargs:
            del form_kwargs["instance"]

        parcel_formset = ParcelFormSet(**form_kwargs)
        return parcel_formset

    def get_context_data(self, **kwargs):
        if "parcel_formset" not in kwargs:
            kwargs["parcel_formset"] = self.get_parcel_formset()
        return super().get_context_data(**kwargs)
