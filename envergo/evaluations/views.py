import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import get_storage_class
from django.db import transaction
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.datastructures import MultiValueDict
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, RedirectView, TemplateView

from envergo.analytics.utils import log_event
from envergo.evaluations.forms import (
    EvaluationSearchForm,
    EvaluationShareForm,
    RequestForm,
    WizardAddressForm,
    WizardContactForm,
    WizardFilesForm,
)
from envergo.evaluations.models import (
    RESULTS,
    Criterion,
    Evaluation,
    Request,
    RequestFile,
)
from envergo.evaluations.tasks import (
    confirm_request_to_admin,
    confirm_request_to_requester,
    share_evaluation_by_email,
)

logger = logging.getLogger(__name__)


class EvaluationSearch(FormView):
    """A simple search form to find evaluations for a project."""

    template_name = "evaluations/search.html"
    form_class = EvaluationSearchForm

    def form_valid(self, form):

        reference = form.cleaned_data.get("reference")
        success_url = reverse("evaluation_detail", args=[reference])
        return HttpResponseRedirect(success_url)


class EvaluationDetail(FormView, DetailView):
    """The complete evaluation detail."""

    template_name = "evaluations/detail.html"
    model = Evaluation
    slug_url_kwarg = "reference"
    slug_field = "reference"
    context_object_name = "evaluation"
    form_class = EvaluationShareForm

    def get_template_names(self):
        """Return which template to use.

        We use THREE different eval templates, depending on the result:
         - soumis
         - non-soumis
         - action requise
        """

        templates = {
            RESULTS.soumis: "evaluations/detail/soumis.html",
            RESULTS.non_soumis: "evaluations/detail/non_soumis.html",
            RESULTS.action_requise: "evaluations/detail/action_requise.html",
        }
        evaluation = self.object
        template_names = [templates.get(evaluation.result)]
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
            criterions = self.object.criterions.all()
            context["criterions"] = criterions

            actions = [
                criterion.get_required_action_display()
                for criterion in criterions
                if criterion.result == RESULTS.action_requise
                and criterion.required_action
            ]
            context["required_actions"] = actions
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.http_method_not_allowed(request)
        return super().post(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        if not self.request.user.is_authenticated:
            form.fields["emails"].disabled = True

        return form

    def form_valid(self, form):
        """Process the "share by email" form."""
        user = self.request.user
        sender_id = user.id
        emails = form.cleaned_data["emails"]
        reference = self.kwargs.get("reference")
        host = self.request.get_host()
        share_evaluation_by_email(reference, host, sender_id, emails)
        msg = _("We forwarded this evaluation to the specified emails.")
        messages.success(self.request, msg)

        return HttpResponseRedirect(self.request.path)

    def form_invalid(self, form):
        msg = _("we could not process your request. Please check for errors below.")
        messages.error(self.request, msg)
        return self.get(self.request, self.args, self.kwargs)


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
                filedicts.append(
                    {"name": file.name, "saved_name": saved_name, "size": file.size}
                )
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["uploaded_files"] = self.get_files_data()
        return context


class RequestEvalWizardReset(WizardStepMixin, RedirectView):
    pattern_name = "request_eval_wizard_step_1"

    query_string = True

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
    success_url = reverse_lazy("request_success")

    def form_valid(self, form):
        """Since this is the last step, process the whole form."""
        super().form_valid(form)

        form_kwargs = self.get_form_kwargs()
        form_kwargs["data"] = self.get_form_data()
        request_form = RequestForm(**form_kwargs)
        if request_form.is_valid():
            return self.request_form_valid(request_form)
        else:
            return self.request_form_invalid(request_form)

    def request_form_valid(self, form):
        request = form.save()
        file_storage = self.get_file_storage()
        filedicts = self.get_files_data()
        logger.warning(f"Saving files: {filedicts}")

        for filedict in filedicts:
            RequestFile.objects.create(
                request=request,
                file=file_storage.open(filedict["saved_name"]),
                name=filedict["name"],
            )

        # Send notifications, once data is commited
        def confirm_request():
            confirm_request_to_requester.delay(request.id, self.request.get_host())
            confirm_request_to_admin.delay(request.id, self.request.get_host())

        transaction.on_commit(confirm_request)

        log_event(
            "evaluation",
            "request",
            self.request.session.session_key,
            request_reference=request.reference,
            request_url=reverse(
                "admin:evaluations_request_change", args=[request.reference]
            ),
        )
        self.reset_data()
        return HttpResponseRedirect(self.get_success_url())

    def request_form_invalid(self, form):
        return HttpResponseRedirect(reverse("request_eval_wizard_reset"))


class RequestEvalWizardStepFiles(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_files.html"
    form_class = WizardFilesForm
    success_url = reverse_lazy("request_eval_wizard_step_2")

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({})


class RequestSuccess(TemplateView):
    template_name = "evaluations/request_success.html"
