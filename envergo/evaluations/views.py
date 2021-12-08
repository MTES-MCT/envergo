from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import get_storage_class
from django.db import transaction
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, FormView, RedirectView, TemplateView
from django.views.generic.edit import CreateView
from ratelimit.decorators import ratelimit

from envergo.evaluations.forms import (
    EvaluationSearchForm,
    RequestForm,
    WizardAddressForm,
    WizardContactForm,
    WizardFilesForm,
)
from envergo.evaluations.models import Criterion, Evaluation, Request, RequestFile
from envergo.evaluations.tasks import (
    confirm_request_to_admin,
    confirm_request_to_requester,
)
from envergo.geodata.forms import ParcelFormSet


class EvaluationSearch(FormView):
    """A simple search form to find evaluations for a project."""

    template_name = "evaluations/search.html"
    form_class = EvaluationSearchForm

    def form_valid(self, form):

        reference = form.cleaned_data.get("reference")
        success_url = reverse("evaluation_detail", args=[reference])
        return HttpResponseRedirect(success_url)


class EvaluationDetail(DetailView):
    """The complete evaluation detail."""

    template_name = "evaluations/detail.html"
    model = Evaluation
    slug_url_kwarg = "reference"
    slug_field = "reference"
    context_object_name = "evaluation"

    def get_template_names(self):
        """Return which template to use.

        We use two different evaluation formats, depending on the fact that
        the project is subject to the Water law.
        """
        if self.object.is_project_subject_to_water_law():
            template_names = ["evaluations/detail_subject.html"]
        else:
            template_names = ["evaluations/detail_non_subject.html"]

        return template_names

    def get_queryset(self):
        qs = Evaluation.objects.select_related("request").prefetch_related(
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
            context.update({"reference": kwargs.get("reference")})
            res = render(request, "evaluations/not_found.html", context, status=404)

        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.object:
            context["criterions"] = self.object.criterions.all()
        return context


class RequestEvaluation(CreateView):
    """A form to request an evaluation for a project."""

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

    # Rate limiting the POST view, as a precaution
    # Indeed, the form is not captcha protected, and the file upload field
    # could fill up the s3 space quickly
    @method_decorator(ratelimit(key="ip", rate="256/d", block=True))
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
            request = form.save()
            parcels = parcel_formset.save()
            request.parcels.set(parcels)

        confirm_request_to_requester.delay(request.id)
        confirm_request_to_admin.delay(request.id, self.request.get_host())

        success_url = reverse("request_success")
        return HttpResponseRedirect(success_url)

    def form_invalid(self, form, parcel_formset):
        return self.render_to_response(
            self.get_context_data(
                form=form,
                parcel_formset=parcel_formset,
                has_errors=True,
                other_non_field_errors=parcel_formset.non_form_errors(),
            )
        )


class RequestSuccess(TemplateView):
    template_name = "evaluations/request_success.html"


class Dashboard(LoginRequiredMixin, TemplateView):
    template_name = "evaluations/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["requests"] = self.get_requests()
        context["evaluations"] = self.get_evaluations()
        return context

    def get_requests(self):
        user_email = self.request.user.email
        return (
            Request.objects.filter(contact_email=user_email)
            .filter(evaluation__isnull=True)
            .order_by("-created_at")
        )

    def get_evaluations(self):
        user_email = self.request.user.email
        return Evaluation.objects.filter(contact_email=user_email).order_by(
            "-created_at"
        )


DATA_KEY = "REQUEST_WIZARD_DATA"
FILES_KEY = "REQUEST_WIZARD_FILES"


class RequestEvalWizardReset(RedirectView):
    pattern_name = "request_eval_wizard_step_1"

    def dispatch(self, request, *args, **kwargs):
        if DATA_KEY in request.session:
            del request.session[DATA_KEY]
            request.session.modified = True
        return super().dispatch(request, *args, **kwargs)


class WizardStepMixin:
    def get_initial(self):
        return self.request.session.get(DATA_KEY, {})

    def form_valid(self, form):
        if DATA_KEY not in self.request.session:
            self.request.session[DATA_KEY] = {}

        if FILES_KEY not in self.request.session:
            self.request.session[FILES_KEY] = {}

        data = form.cleaned_data
        self.request.session[DATA_KEY].update(data)
        self.request.session.modified = True
        return super().form_valid(form)


class RequestEvalWizardStep1(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_address.html"
    form_class = WizardAddressForm
    success_url = reverse_lazy("request_eval_wizard_step_2")


class RequestEvalWizardStep2(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_contact.html"
    form_class = WizardContactForm
    success_url = reverse_lazy("request_eval_wizard_submit")


class RequestEvalWizardStepFiles(FormView):
    template_name = "evaluations/eval_request_wizard_files.html"
    form_class = WizardFilesForm
    success_url = reverse_lazy("request_eval_wizard_submit")

    def form_valid(self, form):
        # TODO
        return JsonResponse({})


class RequestEvalWizardSubmit(FormView):
    template_name = "evaluations/eval_request_wizard_submit.html"
    form_class = RequestForm
    success_url = reverse_lazy("request_success")

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.session.get(DATA_KEY, {}),
                    "files": self.request.session.get(FILES_KEY, {}),
                }
            )
        return kwargs

    def form_valid(self, form):
        request = form.save()
        file_storage = get_storage_class(settings.UPLOAD_FILE_STORAGE)()
        # TODO
        files = []
        for file_dict in files:
            RequestFile.objects.create(
                request=request,
                file=file_storage.open(file_dict["tmp_name"]),
                name=file_dict["name"],
            )
        return super().form_valid(form)

    def form_invalid(self, form):
        # XXX Redirect ?
        return super().form_invalid(form)
