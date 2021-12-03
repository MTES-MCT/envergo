from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, FormView, TemplateView
from django.views.generic.edit import CreateView
from formtools.wizard.storage.exceptions import NoFileStorageConfigured
from formtools.wizard.storage.session import SessionStorage
from formtools.wizard.views import NamedUrlSessionWizardView
from ratelimit.decorators import ratelimit

from envergo.evaluations.forms import (
    EvaluationSearchForm,
    RequestForm,
    WizardAddressForm,
    WizardContactForm,
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


FORMS = [
    ("address", WizardAddressForm),
    ("contact", WizardContactForm),
]


TEMPLATES = {
    "address": "evaluations/eval_request_wizard_address.html",
    "contact": "evaluations/eval_request_wizard_contact.html",
}


class Storage(SessionStorage):
    def set_step_files(self, step, files):
        if files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        if step not in self.data[self.step_files_key]:
            self.data[self.step_files_key][step] = {}

        if not files:
            return

        for field in files.keys():
            field_files = files.getlist(field)
            file_dicts = []
            for field_file in field_files:
                tmp_filename = self.file_storage.save(field_file.name, field_file)
                file_dict = {
                    "tmp_name": tmp_filename,
                    "name": field_file.name,
                    "content_type": field_file.content_type,
                    "size": field_file.size,
                    "charset": field_file.charset,
                }
                file_dicts.append(file_dict)

            self.data[self.step_files_key][step][field] = file_dicts

    def get_step_files(self, step):
        wizard_files = self.data[self.step_files_key].get(step, {})

        if wizard_files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        files = {}
        for field, field_files in wizard_files.items():
            files[field] = []

            for field_dict in field_files:
                field_dict = field_dict.copy()
                tmp_name = field_dict.pop("tmp_name")
                if (step, field) not in self._files:
                    self._files[(step, field)] = UploadedFile(
                        file=self.file_storage.open(tmp_name), **field_dict
                    )

                files[field] = self._files[(step, field)]
        return files or None

    def reset(self):
        # Store unused temporary file names in order to delete them
        # at the end of the response cycle through a callback attached in
        # `update_response`.
        wizard_files = self.data[self.step_files_key]
        for step_files in wizard_files.values():
            for step_field_files in step_files.values():
                for step_file in step_field_files:
                    self._tmp_files.append(step_file["tmp_name"])
        self.init_data()


class RequestEvalWizard(NamedUrlSessionWizardView):
    storage_name = "envergo.evaluations.views.Storage"
    form_list = FORMS
    file_storage = get_storage_class(settings.UPLOAD_FILE_STORAGE)()

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, form_dict, **kwargs):
        data = self.get_all_cleaned_data()
        request_form = RequestForm(data)
        request = request_form.save()

        files = self.storage.data[self.storage.step_files_key]["contact"][
            "contact-additional_files"
        ]
        for file_dict in files:
            RequestFile.objects.create(
                request=request,
                file=self.file_storage.open(file_dict["tmp_name"]),
                name=file_dict["name"],
            )

        success_url = reverse("request_success")
        return HttpResponseRedirect(success_url)
