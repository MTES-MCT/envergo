from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import get_storage_class
from django.db import transaction
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.datastructures import MultiValueDict
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
FILES_FIELD = "additional_files"


class WizardStepMixin:
    """Common code for a form split into several steps.

    The whole form is split into several subforms, and each valid form is
    saved in session until the last step.

    Then, all form data is combined to save a single object.

    Handling file is a little annoying because they cannot be stored in session,
    so they have to be uploaded to the file storage right away.
    """

    def get_form_data(self):
        data = MultiValueDict(self.request.session.get(DATA_KEY, {}))
        return data

    def get_files_data(self):
        return self.request.session.get(FILES_KEY, [])

    def get_initial(self):
        return self.get_form_data().dict()

    def form_valid(self, form):
        """Save the form data in session."""

        if DATA_KEY not in self.request.session:
            self.request.session[DATA_KEY] = MultiValueDict({})

        if FILES_KEY not in self.request.session:
            self.request.session[FILES_KEY] = []

        # Save form data to session
        data = self.get_form_data()
        data.update(form.data)
        self.request.session[DATA_KEY] = dict(data.lists())

        # Save uploaded files using the file storage
        if FILES_FIELD in self.request.FILES:
            file_storage = self.get_file_storage()
            files = self.request.FILES.getlist(FILES_FIELD)
            filedicts = []
            for file in files:
                saved_name = file_storage.save(file.name, file)
                filedicts.append({"name": file.name, "saved_name": saved_name})
            self.request.session[FILES_KEY] += filedicts

        self.request.session.modified = True
        return super().form_valid(form)

    def get_file_storage(self):
        file_storage = get_storage_class(settings.UPLOAD_FILE_STORAGE)()
        return file_storage

    def reset_data(self):
        """Clear tmp form data stored in session, and uploaded files."""

        self.request.session.pop(DATA_KEY, None)

        file_storage = self.get_file_storage()
        filedicts = self.request.session.get(FILES_KEY, [])
        for filedict in filedicts:
            saved_name = filedict["saved_name"]
            file_storage.delete(saved_name)

        self.request.session.pop(FILES_KEY, None)
        self.request.session.modified = True


class RequestEvalWizardReset(WizardStepMixin, RedirectView):
    pattern_name = "request_eval_wizard_step_1"

    def dispatch(self, request, *args, **kwargs):
        self.reset_data()
        return super().dispatch(request, *args, **kwargs)


class RequestEvalWizardStep1(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_address.html"
    form_class = WizardAddressForm
    success_url = reverse_lazy("request_eval_wizard_step_2")


class RequestEvalWizardStep2(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_contact.html"
    form_class = WizardContactForm
    success_url = reverse_lazy("request_eval_wizard_submit")


class RequestEvalWizardStepFiles(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_files.html"
    form_class = WizardFilesForm
    success_url = reverse_lazy("request_eval_wizard_submit")

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({})


class RequestEvalWizardSubmit(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_submit.html"
    form_class = RequestForm
    success_url = reverse_lazy("request_success")

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        kwargs.update({"data": self.get_form_data()})
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        request = form.save()
        file_storage = self.get_file_storage()
        filedicts = self.get_files_data()
        for filedict in filedicts:
            RequestFile.objects.create(
                request=request,
                file=file_storage.open(filedict["saved_name"]),
                name=filedict["name"],
            )

        self.reset_data()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return HttpResponseRedirect(reverse("request_eval_wizard_reset"))
