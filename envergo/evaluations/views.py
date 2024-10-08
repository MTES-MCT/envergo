import logging
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Q
from django.db.models.query import Prefetch
from django.http.response import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.datastructures import MultiValueDict
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    DetailView,
    FormView,
    RedirectView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import BaseFormView

from envergo.analytics.utils import is_request_from_a_bot, log_event
from envergo.evaluations.forms import (
    EvaluationSearchForm,
    RequestForm,
    WizardAddressForm,
    WizardContactForm,
    WizardFilesForm,
)
from envergo.evaluations.models import (
    Evaluation,
    EvaluationVersion,
    Request,
    RequestFile,
)
from envergo.evaluations.tasks import (
    confirm_request_to_admin,
    confirm_request_to_requester,
    post_evalreq_to_automation,
)
from envergo.geodata.models import Department
from envergo.moulinette.views import MoulinetteMixin
from envergo.utils.urls import update_qs

logger = logging.getLogger(__name__)


class ShortUrlAdminRedirectView(RedirectView):
    """Create a shorter url format for evaluations.

    This is useful for posting in our crm.
    """

    def get_redirect_url(self, *args, **kwargs):
        reference = kwargs.get("reference")
        try:
            evaluation = Evaluation.objects.get(reference=reference)
        except Evaluation.DoesNotExist:
            raise Http404
        redirect_url = reverse(
            "admin:evaluations_evaluation_change", args=[evaluation.uid]
        )
        return redirect_url


class EvaluationSearch(FormView):
    """A simple search form to find evaluations for a project."""

    template_name = "evaluations/search.html"
    form_class = EvaluationSearchForm

    def form_valid(self, form):
        reference = form.cleaned_data.get("reference")
        success_url = reverse("evaluation_detail", args=[reference])
        return HttpResponseRedirect(success_url)


class EvaluationDetailMixin:
    """Mixin for all views working on a single evaluation.

    Note: by excluding the moulinette_url="", we discard all the legacy evaluations
    that were manually created, allowing us a clean refactoring.

    This is a temporary step, and this filter will be removed once all the legacy
    evaluations have been safely discarded from the db.
    """

    model = Evaluation
    slug_url_kwarg = "reference"
    slug_field = "reference"

    def get_queryset(self):
        qs = (
            Evaluation.objects.exclude(moulinette_url="")
            .select_related("request")
            .prefetch_related(
                Prefetch(
                    "versions",
                    queryset=EvaluationVersion.objects.order_by("-created_at"),
                )
            )
        )
        return qs


class EvaluationDetail(
    EvaluationDetailMixin, MoulinetteMixin, BaseFormView, DetailView
):
    """Display an evaluation detail page, where the result is generated by the Moulinette.

    Note: This view inherits from FormView because it uses a MoulinetteForm to
    validate moulinette data.
    """

    event_category = "evaluation"
    event_action = "visit"

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_moulinette_raw_data(self):
        return self.object.moulinette_params

    def get_template_names(self):
        """Check wich template to use depending on the moulinette result."""

        return ["evaluations/detail.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_map_static"] = True
        context["source"] = "evaluation"
        current_url = self.request.build_absolute_uri()

        share_btn_url = update_qs(current_url, {"mtm_campaign": "share-ar"})
        share_print_url = update_qs(current_url, {"mtm_campaign": "print-ar"})

        context["current_url"] = current_url
        context["share_btn_url"] = share_btn_url
        context["share_print_url"] = share_print_url
        context["evaluation_content"] = self.get_evaluation_content()
        return context

    def get_evaluation_content(self):
        """Select the correct version to display."""

        # Staff can preview draft evaluations
        selected_version_id = int(self.request.GET.get("version", -1))
        selected_version = next(
            (v for v in self.object.versions.all() if v.id == selected_version_id),
            None,
        )

        # By default, we display the published version
        published_version = next(
            (v for v in self.object.versions.all() if v.published), None
        )

        if selected_version and self.request.user.is_staff:
            content = selected_version.content
        elif published_version:
            content = published_version.content
        else:
            content = self.object.render_content()

        return content

    def get(self, request, *args, **kwargs):
        # The Method Resolution Order (MRO) of python makes sure that
        # the `get` method is called from the `BaseDetailView` subclass,
        # not the `MoulinetteResult` subclass.
        # This is important because the `MoulinetteResult.get` method
        # also calls the `log_moulinette_event` method with different
        # arguments.

        try:
            self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            res = self.render_to_response(context)
        except Http404:
            self.object = None
            context = {"reference": kwargs.get("reference")}
            res = render(request, "evaluations/not_found.html", context, status=404)

        if self.object:

            # When a tally form is redirected, we use this variable to display
            # a success message.
            tally = request.GET.get("tally", "")
            if tally:
                messages.success(request, "Nous avons bien reçu votre réponse.")

            if not is_request_from_a_bot(request):
                self.log_moulinette_event(
                    self.moulinette, request_reference=self.object.reference
                )

        return res

    def should_activate_optional_criteria(self):
        return True


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
            Request.objects.filter(urbanism_department_emails__contains=[user_email])
            .filter(evaluation__isnull=True)
            .order_by("-created_at")
        )

    def get_evaluations(self):
        user_email = self.request.user.email
        url_isnull = Q(moulinette_url="")
        invalid_evals = url_isnull

        evals = (
            Evaluation.objects.filter(urbanism_department_emails__contains=[user_email])
            .exclude(invalid_evals)
            .order_by("-created_at")
        )
        return evals


DATA_KEY = "REQUEST_WIZARD_DATA"
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

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.get_form_data().dict())
        return self.get_form_data().dict()

    def form_valid(self, form):
        """Save the form data in session."""

        if DATA_KEY not in self.request.session:
            self.request.session[DATA_KEY] = MultiValueDict({})

        # Save form data to session
        data = self.get_form_data()
        data.update(form.data)
        self.request.session[DATA_KEY] = dict(data.lists())

        # Make sure django updates session data
        self.request.session.modified = True
        return super().form_valid(form)

    def get_file_storage(self):
        file_storage = storages["upload"]
        return file_storage

    def reset_data(self):
        """Clear tmp form data stored in session."""

        self.request.session.pop(DATA_KEY, None)
        self.request.session.modified = True


class RequestEvalWizardHome(TemplateView):
    template_name = "evaluations/eval_request_wizard_home.html"


class RequestEvalWizardReset(WizardStepMixin, RedirectView):
    """Resets all wizard data then redirects to first step."""

    pattern_name = "request_eval_wizard_step_1"
    query_string = True

    def dispatch(self, request, *args, **kwargs):
        self.reset_data()
        return super().dispatch(request, *args, **kwargs)


class RequestEvalWizardStep1(WizardStepMixin, FormView):
    template_name = "evaluations/eval_request_wizard_address.html"
    form_class = WizardAddressForm
    success_url = reverse_lazy("request_eval_wizard_step_2")

    def form_invalid(self, form):
        is_department_unavailable = form.has_error(
            "department", code="unavailable_department"
        )
        if is_department_unavailable:
            return HttpResponseRedirect(
                reverse(
                    "request_eval_wizard_unavailable_department",
                    args=[form.cleaned_data["department"].department],
                )
            )

        return super().form_invalid(form)


class RequestEvalWizardDepartmentUnavailable(TemplateView):
    template_name = (
        "evaluations/eval_request_wizard_address_unavailable_department.html"
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = Department.objects.filter(
            department=kwargs.get("department")
        ).first()
        context["department"] = department
        return context


class RequestEvalWizardStep2(WizardStepMixin, FormView):
    """Second step of the wizard.

    Even though this is a 3 steps wizard, we actually save the object at the
    end of this step.

    That is because the third step only features the file upload widget, and
    we need an existing object in the db to attach the files to.
    """

    template_name = "evaluations/eval_request_wizard_contact.html"
    form_class = WizardContactForm

    # This method is called by the `super()` class, at a moment when we don't
    # know the url yet. So we just return a dummy url.
    def get_success_url(self):
        success_url = reverse("request_eval_wizard_step_3", args=["XXXXXX"])
        return success_url

    def form_valid(self, form):
        """Process the whole form and save object to the db.

        This `form_valid` is called when the current step form
        (WizardContactForm) is valid.
        """
        super().form_valid(form)

        form_kwargs = self.get_form_kwargs()
        form_kwargs["data"] = self.get_form_data()
        request_form = RequestForm(**form_kwargs)
        if request_form.is_valid():
            return self.request_form_valid(request_form)
        else:
            return self.request_form_invalid(request_form)

    def request_form_valid(self, form):
        """This is called when all the combined step forms are valid."""

        request = form.save()
        self.reset_data()
        success_url = reverse("request_eval_wizard_step_3", args=[request.reference])
        return HttpResponseRedirect(success_url)

    def request_form_invalid(self, form):
        return HttpResponseRedirect(reverse("request_eval_wizard_reset"))


class RequestEvalWizardStep3(WizardStepMixin, UpdateView):
    template_name = "evaluations/eval_request_wizard_files.html"
    model = Request
    form_class = WizardFilesForm
    slug_field = "reference"
    slug_url_kwarg = "reference"
    context_object_name = "evalreq"

    def get_success_url(self):
        url = reverse("request_success", args=[self.object.reference])
        return url

    def form_valid(self, form):

        request = form.instance

        # Send notifications, once data is commited
        def confirm_request():
            request.submitted = True
            request.save()
            confirm_request_to_requester.delay(request.id, self.request.get_host())
            confirm_request_to_admin.delay(request.id, self.request.get_host())
            post_evalreq_to_automation.delay(request.id, self.request.get_host())

        # Special case, hackish
        # The product is often used for demo purpose. In that case, we don't
        # want to send confirmation emails or any other notifications.
        if (
            request.submitted is False
            and settings.TEST_EMAIL not in request.urbanism_department_emails
        ):
            transaction.on_commit(confirm_request)
            mtm_keys = {
                k: v for k, v in self.request.session.items() if k.startswith("mtm_")
            }
            log_event(
                "evaluation",
                "request",
                self.request,
                request_reference=request.reference,
                request_url=reverse(
                    "admin:evaluations_request_change", args=[request.id]
                ),
                **mtm_keys,
            )

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        files_qs = RequestFile.objects.filter(request=self.object)
        files = []
        for file in files_qs:
            try:
                file_obj = {"id": file.id, "name": file.name, "size": file.file.size}
            except FileNotFoundError:
                # This means the EvaluationFile object exists in db but the
                # actual file is missing from storage.
                file_obj = {"id": file.id, "name": file.name, "size": 0}

            files.append(file_obj)

        context = super().get_context_data(**kwargs)
        context["max_files"] = settings.MAX_EVALREQ_FILES
        context["uploaded_files"] = files
        context["request_submitted"] = self.object.submitted
        return context


@method_decorator(csrf_exempt, name="dispatch")
class RequestEvalWizardStep3Upload(WizardStepMixin, UpdateView):
    """Handle ajax file uploads and deletions."""

    model = Request
    form_class = WizardFilesForm
    slug_field = "reference"
    slug_url_kwarg = "reference"
    context_object_name = "evalreq"

    def form_valid(self, form):
        """This is called when a file is uploaded with dropzone."""

        try:
            # Make sure that the file limit is respected
            files_qs = RequestFile.objects.filter(request=self.object)
            current_files = files_qs.count()
            max_files = settings.MAX_EVALREQ_FILES
            if current_files >= max_files:
                return JsonResponse(
                    {
                        "error": f"Vous ne pouvez pas envoyer plus de {max_files} fichiers."
                    },
                    status=400,
                )

            # Save uploaded files using the file storage
            file = self.request.FILES.get(FILES_FIELD)
            if not file:
                return JsonResponse(
                    {"error": "Aucun fichier n'a été reçu."},
                    status=400,
                )

            evalreq = RequestFile.objects.create(
                request=self.object,
                file=file,
                name=file.name,
            )
            return JsonResponse({"id": evalreq.id})

        except Exception:
            return JsonResponse(
                {
                    "error": "Le fichier n'a pas pu être enregistré. Veuillez ré-essayer."
                },
                status=500,
            )

    def form_invalid(self, form):
        return JsonResponse(
            {"error": "Le fichier n'a pas pu être enregistré. Veuillez ré-essayer."},
            status=400,
        )

    def delete(self, request, *args, **kwargs):
        """This is called when a file is removed with dropzone."""

        try:
            self.object = self.get_object()

            file_id = self.request.GET.get("file_id")
            files_qs = RequestFile.objects.filter(request=self.object)
            file_obj = files_qs.get(id=file_id)

            file_storage = self.get_file_storage()
            file_storage.delete(file_obj.file.name)
            file_obj.delete()
            return JsonResponse({})

        except RequestFile.DoesNotExist:
            return JsonResponse(
                {"error": "Ce fichier n'existe pas."},
                status=400,
            )


class RequestSuccess(DetailView):
    template_name = "evaluations/request_success.html"
    model = Request
    slug_field = "reference"
    slug_url_kwarg = "reference"
    context_object_name = "evalreq"


class SelfDeclaration(EvaluationDetailMixin, DetailView):
    template_name = "evaluations/self_declaration.html"

    def get(self, request, *args, **kwargs):
        res = super().get(request, *args, **kwargs)
        evaluation = self.object
        metadata = {
            "request_reference": evaluation.reference,
            "source": request.GET.get("source", ""),
        }
        log_event("compliance", "form-visit", request, **metadata)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tally_form_id"] = settings.SELF_DECLARATION_FORM_ID
        context["reference"] = self.object.reference
        context["address"] = quote_plus(self.object.address, safe="")
        context["application_number"] = self.object.application_number
        context["redirect_url"] = f"{self.object.get_absolute_url()}?tally=ok"
        return context
