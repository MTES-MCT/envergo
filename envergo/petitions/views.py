import datetime
import logging
import os
import re
import shutil
import tempfile
from collections import defaultdict
from urllib.parse import parse_qs, urlparse

import fiona
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.postgres.expressions import ArraySubquery
from django.contrib.sites.models import Site
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    RedirectView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin
from fiona import Feature, Geometry, Properties
from pyproj import Transformer
from shapely.ops import transform

from envergo.analytics.utils import (
    get_matomo_tags,
    get_user_type,
    log_event,
    update_url_with_matomo_params,
)
from envergo.geodata.utils import get_google_maps_centered_url, get_ign_centered_url
from envergo.hedges.models import EPSG_LAMB93, EPSG_WGS84, TO_PLANT
from envergo.hedges.services import PlantationEvaluator, PlantationResults
from envergo.moulinette.models import ConfigHaie, MoulinetteHaie
from envergo.moulinette.utils import MoulinetteUrl
from envergo.petitions.demarches_simplifiees.client import DemarchesSimplifieesError
from envergo.petitions.forms import (
    PetitionProjectForm,
    PetitionProjectInstructorEspecesProtegeesForm,
    PetitionProjectInstructorMessageForm,
    PetitionProjectInstructorNotesForm,
    ProcedureForm,
    RequestAdditionalInfoForm,
    ResumeProcessingForm,
    SimulationForm,
)
from envergo.petitions.models import (
    DECISIONS,
    DOSSIER_STATES,
    LOG_TYPES,
    STAGES,
    InvitationToken,
    LatestMessagerieAccess,
    PetitionProject,
    Simulation,
    StatusLog,
)
from envergo.petitions.services import (
    DEMARCHES_SIMPLIFIEES_STATUS_MAPPING,
    PetitionProjectCreationAlert,
    PetitionProjectCreationProblem,
    compute_instructor_informations_ds,
    extract_data_from_fields,
    get_context_from_ds,
    get_messages_and_senders_from_ds,
    get_project_context,
    send_message_dossier_ds,
    update_demarches_simplifiees_status,
)
from envergo.users.models import User
from envergo.utils.mattermost import notify
from envergo.utils.tools import generate_key
from envergo.utils.urls import extract_param_from_url, remove_mtm_params, update_qs

logger = logging.getLogger(__name__)

INVITATION_TOKEN_MATOMO_TAG = "invitation_dossier"


class PetitionProjectList(LoginRequiredMixin, ListView):
    """View list for PetitionProject"""

    template_name = "haie/petitions/instructor_dossier_list.html"
    paginate_by = 30

    def get_queryset(self):
        """Override queryset filtering projects from user departments

        Returns
        - all objects if user is superuser
        - filtered objects on department if user is instructor
        - none object if user is not instructor or not superuser
        """
        current_user = self.request.user

        messagerie_access_qs = LatestMessagerieAccess.objects.filter(
            user=current_user
        ).filter(project=OuterRef("pk"))
        followers_qs = (
            User.objects.filter(is_superuser=False)
            .filter(is_instructor=True)
            .filter(followed_petition_projects=OuterRef("pk"))
            .filter(departments=OuterRef("department"))
        )

        queryset = (
            PetitionProject.objects.exclude(
                demarches_simplifiees_state__exact=DOSSIER_STATES.draft
            )
            .select_related("hedge_data", "department")
            .prefetch_related(
                Prefetch(
                    "status_history",
                    queryset=StatusLog.objects.all().order_by("-created_at"),
                )
            )
            .annotate(messagerie_access=Subquery(messagerie_access_qs.values("access")))
            .annotate(
                latest_access=Coalesce("messagerie_access", current_user.date_joined)
            )
            .annotate(followers=ArraySubquery(followers_qs.values("email")))
            .annotate(
                followed_up=Exists(
                    PetitionProject.followed_by.through.objects.filter(
                        petitionproject_id=OuterRef("pk"),
                        user_id=current_user.pk,
                    )
                )
            )
            .order_by("-demarches_simplifiees_date_depot", "-created_at")
        )
        # Filter on current user status
        if current_user.is_superuser:
            # don't filter the queryset
            pass
        elif current_user.access_haie:
            user_departments = current_user.departments.defer("geometry").all()
            queryset = queryset.filter(
                Q(department__in=user_departments)
                | Q(invitation_tokens__user_id=current_user.id)
            ).distinct()
        else:
            queryset = queryset.none()

        return queryset

    def filter_results(self, queryset):
        """Filter queryset on request GET params"""
        request_filters = self.request.GET.getlist("f", [])
        if "mes_dossiers" in request_filters:
            queryset = queryset.filter(followed_up=True)

        if "dossiers_sans_instructeur" in request_filters:
            is_instructor = Q(followed_by__is_instructor=True) & Q(
                followed_by__is_superuser=False
            )
            queryset = queryset.exclude(is_instructor)

        return queryset

    def get_context_data(self, **kwargs):
        """Filter results and add info on each object"""
        all_results = self.object_list
        filtered_results = self.filter_results(all_results)
        kwargs["object_list"] = filtered_results

        context = super().get_context_data(**kwargs)

        # Check if all results is empty when filters are in querystring
        if filtered_results:
            context["user_can_view_one_petition_project"] = True
        else:
            context["user_can_view_one_petition_project"] = all_results.exists()

        # Add city and organization to each obj
        objects = context["object_list"]
        for obj in objects:
            dossier = obj.prefetched_dossier
            if dossier:
                config = self.get_project_config(obj)
                city, organization, _ = extract_data_from_fields(config, dossier)
                obj.city = city
                obj.organization = organization

        return context

    def get_project_config(self, project):
        """Return the Config object associated with this project.

        Internally builds a cache by prefetching all ConfigHaie for the departments
        present in `object_list` in a single query.
        """

        def _build_cache():
            """Build a list of of config objects per department."""

            # Extract the set of departments from the list of projects
            department_ids = {obj.department_id for obj in self.object_list}

            # For each department, extract the list of existing configs
            configs_by_dept = defaultdict(list)
            for config in ConfigHaie.objects.filter(department_id__in=department_ids):
                configs_by_dept[config.department_id].append(config)

            return configs_by_dept

        if not hasattr(self, "_config_cache"):
            self._config_cache = _build_cache()
        configs_by_dept = self._config_cache

        department_id = project.department_id
        project_date = project.created_at.date()

        for config in configs_by_dept[department_id]:
            # If there is no range, then it's the only possible config for this
            # department
            if config.validity_range is None:
                return config

            # Config is not valid yet, skip
            if (
                config.validity_range.lower
                and project_date < config.validity_range.lower
            ):
                continue

            # Config is not valid anymore, skip
            if (
                config.validity_range.upper
                and project_date >= config.validity_range.upper
            ):
                continue

            # We found a valid config
            # Since config cannot overlap, it must be the only valid one
            return config

        return None


class PetitionProjectCreate(FormView):
    form_class = PetitionProjectForm

    def dispatch(self, request, *args, **kwargs):
        # store alerts in the request object to notify admins if needed
        if request.method == "GET":
            if request.user.is_authenticated:
                url = reverse("petition_project_list")
            else:
                url = reverse("home")

            return HttpResponseRedirect(url)

        request.alerts = PetitionProjectCreationAlert(request)
        res = super().dispatch(request, *args, **kwargs)

        if len(request.alerts) > 0:
            notify(request.alerts.compute_message(), "haie")
        return res

    def form_valid(self, form):

        form.instance.hedge_data_id = extract_param_from_url(
            form.cleaned_data["moulinette_url"], "haies"
        )

        with transaction.atomic():
            petition_project = form.save()
            read_only_url = reverse(
                "petition_project_auto_redirection",
                kwargs={"reference": petition_project.reference},
            )

            demarche_simplifiee_url, dossier_number = self.pre_fill_demarche_simplifiee(
                petition_project
            )

            if not demarche_simplifiee_url:
                res = self.form_invalid(form)
                # Rollback the transaction to avoid saving the petition project
                transaction.set_rollback(True)
            else:
                petition_project.demarches_simplifiees_dossier_number = dossier_number
                petition_project.save()

                StatusLog.objects.create(
                    petition_project=petition_project,
                    update_comment="Création initiale",
                )

                Simulation.objects.create(
                    project=petition_project,
                    is_initial=True,
                    is_active=True,
                    moulinette_url=petition_project.moulinette_url,
                    comment="Simulation initiale",
                )

                log_event(
                    "demande",
                    "creation",
                    self.request,
                    **petition_project.get_log_event_data(),
                    user_type=get_user_type(self.request.user),
                    **get_matomo_tags(self.request),
                )

                self.request.alerts.petition_project = petition_project

                res = JsonResponse(
                    {
                        "demarche_simplifiee_url": demarche_simplifiee_url,
                        "read_only_url": read_only_url,
                    }
                )

        return res

    def pre_fill_demarche_simplifiee(self, project):
        """Send a http request to pre-fill a dossier on demarches-simplifiees.fr based on moulinette data.

        Return the url of the created dossier if successful, None otherwise
        """

        moulinette_url = project.moulinette_url
        parsed_url = urlparse(moulinette_url)
        moulinette_data = parse_qs(parsed_url.query)
        # Flatten the dictionary
        for key, value in moulinette_data.items():
            if isinstance(value, list) and len(value) == 1:
                moulinette_data[key] = value[0]
        department = moulinette_data.get("department")  # department is mandatory
        if not department:
            logger.error(
                "Moulinette URL for guichet unique de la haie should always contain a department to "
                "start a demarche simplifiée",
                extra={"moulinette_url": moulinette_url},
            )
            return None

        moulinette_data["haies"] = project.hedge_data
        config = ConfigHaie.objects.select_related("department").get(
            department__department=department
        )  # it should always exist, otherwise the simulator would not be available
        self.request.alerts.config = config
        demarche_id = config.demarche_simplifiee_number

        if not demarche_id:
            logger.error(
                "An activated department should always have a demarche_simplifiee_number",
                extra={"haie config": config.id, "department": department},
            )

            self.request.alerts.append(
                PetitionProjectCreationProblem(
                    "missing_demarche_simplifiee_number", is_fatal=True
                )
            )
            return None

        api_url = f"{settings.DEMARCHES_SIMPLIFIEES['PRE_FILL_API_URL']}demarches/{demarche_id}/dossiers"
        body = {}
        form_data = {"initial": moulinette_data, "data": moulinette_data}
        moulinette = MoulinetteHaie(form_data)
        for field in config.demarche_simplifiee_pre_fill_config:
            if "id" not in field or "value" not in field:
                logger.error(
                    "Invalid pre-fill configuration for a dossier on demarches-simplifiees.fr",
                    extra={"haie config": config.id, "field": field},
                )

                self.request.alerts.append(
                    PetitionProjectCreationProblem(
                        "invalid_prefill_field",
                        {
                            "field": field,
                        },
                    )
                )
                continue

            body[f"champ_{field['id']}"] = self.get_value_from_source(
                project,
                moulinette,
                field["value"],
                field.get("mapping", {}),
                config,
            )

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"\nrequest.url: {api_url}"
                f"\nrequest.body: {body}"
            )
            return None, None

        response = requests.post(
            api_url, json=body, headers={"Content-Type": "application/json"}
        )
        redirect_url, dossier_number = None, None
        if 200 <= response.status_code < 400:
            data = response.json()
            redirect_url = data.get("dossier_url")
            dossier_number = data.get("dossier_number")
        else:
            logger.error(
                "Error while pre-filling a dossier on demarches-simplifiees.fr",
                extra={
                    "api_url": response.request.url,
                    "request_body": response.request.body,
                    "status_code": response.status_code,
                    "response.text": response.text,
                },
            )
            self.request.alerts.append(
                PetitionProjectCreationProblem(
                    "ds_api_http_error",
                    {
                        "response": response,
                        "api_url": api_url,
                        "request_body": body,
                    },
                    is_fatal=True,
                )
            )
        return redirect_url, dossier_number

    def get_value_from_source(
        self, petition_project, moulinette, source, mapping, config
    ):
        """Get the value to pre-fill a dossier on demarches-simplifiees.fr from a source.

        Available sources are listed by this method : ConfigHaie.get_demarche_simplifiee_value_sources()
        Depending on the source, the value comes from the moulinette data, the moulinette result or the moulinette url.
        Then it will map the value if a mapping is provided.
        """
        if source == "url_moulinette":
            value = petition_project.moulinette_url
        elif source == "url_projet":
            value = self.request.build_absolute_uri(
                reverse(
                    "petition_project",
                    kwargs={"reference": petition_project.reference},
                )
            )
        elif source == "ref_projet":
            value = petition_project.reference
        elif source == "plantation_adequate":
            haies = moulinette.catalog.get("haies")
            value = (
                PlantationEvaluator(moulinette, haies).result
                == PlantationResults.Adequate.value
                if haies
                else False
            )
        elif source == "vieil_arbre":
            haies = moulinette.catalog.get("haies")
            if haies:
                value = haies.is_removing_old_tree()
        elif source == "sur_talus_d":
            haies = moulinette.catalog.get("haies")
            value = (
                any(h.prop("sur_talus") for h in haies.hedges_to_remove())
                if haies
                else False
            )
        elif source == "sur_talus_p":
            haies = moulinette.catalog.get("haies")
            value = (
                any(h.prop("sur_talus") for h in haies.hedges_to_plant())
                if haies
                else False
            )
        elif source == "proximite_mare":
            haies = moulinette.catalog.get("haies")
            if haies:
                value = haies.is_removing_near_pond()
        elif source.endswith(".result"):
            regulation_slug = source[:-7]
            regulation_result = getattr(moulinette, regulation_slug, None)
            if regulation_result is None:
                logger.warning(
                    "Unable to get the regulation result to pre-fill a démarche simplifiée",
                    extra={
                        "regulation_slug": regulation_slug,
                        "moulinette_url": petition_project.moulinette_url,
                        "haie config": config.id,
                    },
                )
                self.request.alerts.append(
                    PetitionProjectCreationProblem(
                        "missing_source_regulation",
                        {
                            "source": source,
                            "regulation_slug": regulation_slug,
                        },
                    )
                )

                value = None
            else:
                value = regulation_result.result
        elif source.endswith(".result_code"):
            criteria_path = source[:-12].split(".")
            regulation_slug = criteria_path[0]
            criteria_slug = criteria_path[1]
            regulation = getattr(moulinette, regulation_slug, None)
            criteria = getattr(regulation, criteria_slug, None)
            if criteria is None:
                logger.warning(
                    "Unable to get the criteria result code to pre-fill a démarche simplifiée",
                    extra={
                        "source": source,
                        "moulinette_url": petition_project.moulinette_url,
                        "haie config": config.id,
                    },
                )
                self.request.alerts.append(
                    PetitionProjectCreationProblem(
                        "missing_source_criterion",
                        {
                            "source": source,
                            "criterion_slug": f"{regulation_slug} > {criteria_slug}",
                        },
                    )
                )

                value = None
            else:
                value = criteria.result_code
        else:
            if source in moulinette.catalog:
                value = moulinette.catalog[source]
            else:
                logger.warning(
                    "Unable to get the moulinette value to pre-fill a démarche simplifiée",
                    extra={
                        "source": source,
                        "moulinette_url": petition_project.moulinette_url,
                        "haie config": config.id,
                    },
                )

                self.request.alerts.append(
                    PetitionProjectCreationProblem(
                        "missing_source_moulinette",
                        {
                            "source": source,
                        },
                    )
                )
                value = None

        if mapping:
            # if the mapping object is not empty but do not contain the value, log an info
            if value not in mapping:
                logger.info(
                    "The value to pre-fill a dossier on demarches-simplifiees.fr is not in the mapping",
                    extra={
                        "source": source,
                        "mapping": mapping,
                        "moulinette_url": petition_project.moulinette_url,
                        "haie config": config.id,
                    },
                )
                self.request.alerts.append(
                    PetitionProjectCreationProblem(
                        "mapping_missing_value",
                        {
                            "source": source,
                            "value": value,
                            "mapping": mapping,
                        },
                    )
                )

        mapped_value = mapping.get(value, value)

        # Handle boolean values as strings 😞
        return {
            True: "true",
            False: "false",
        }.get(mapped_value, mapped_value)

    def form_invalid(self, form):
        logger.error("Unable to create a petition project", extra={"form": form})

        self.request.alerts.form = form
        self.request.alerts.user_error_reference = generate_key()

        if form.errors:
            self.request.alerts.append(
                PetitionProjectCreationProblem("invalid_form", is_fatal=True)
            )

        if len(self.request.alerts) == 0:
            self.request.alerts.append(
                PetitionProjectCreationProblem("unknown_error", is_fatal=True)
            )

        return JsonResponse(
            {
                "error_title": "Un problème technique empêche la création de votre dossier.",
                "error_body": f"""
                Nous avons été notifiés et travaillons à la résolution de cette erreur.
                <br/>
                Identifiant de l’erreur : {self.request.alerts.user_error_reference.upper()}
                <br/>
                Merci de vous faire connaître en nous transmettant cet identifiant en nous écrivant à \
                contact@haie.beta.gouv.fr
                <br/>
                Nous vous accompagnerons pour vous permettre de déposer votre demande sans encombres.""",
            },
            status=400,
        )


class PetitionProjectDetail(DetailView):
    template_name = "haie/moulinette/petition_project.html"
    queryset = PetitionProject.objects.all()
    slug_field = "reference"
    slug_url_kwarg = "reference"

    def get(self, request, *args, **kwargs):
        result = super().get(request, *args, **kwargs)

        # Log the consultation event only if it is not after an automatic redirection due to dossier creation
        if not request.session.pop("auto_redirection", False):
            log_event(
                "simulateur",
                "consultation",
                self.request,
                **self.object.get_log_event_data(),
                user_type=get_user_type(self.request.user),
                **get_matomo_tags(self.request),
            )

        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        moulinette = self.object.get_moulinette()

        if moulinette.has_missing_data():
            # this should not happen, unless we have stored an incomplete project
            # If we add some new regulations, or adding evaluators on existing ones, we could have obsolete moulinette
            # we should implement static simulation/project to avoid this case.
            logger.warning(
                "A petition project has missing data. This should not happen unless regulations have changed."
                "We should implement static simulation/project to avoid this case.",
                extra={"reference": self.object.reference},
            )
            raise NotImplementedError("We do not handle uncompleted project")

        context["petition_project"] = self.object
        context["moulinette"] = moulinette
        context.update(moulinette.catalog)
        context["base_result"] = moulinette.get_result_template()
        context["is_read_only"] = True

        context["plantation_evaluation"] = PlantationEvaluator(
            moulinette, moulinette.catalog["haies"]
        )
        context["demarches_simplifiees_dossier_number"] = (
            self.object.demarches_simplifiees_dossier_number
        )
        context["created_at"] = self.object.created_at
        context["demarches_simplifiees_date_depot"] = (
            self.object.demarches_simplifiees_date_depot
        )
        plantation_url = reverse(
            "input_hedges",
            args=[
                moulinette.department.department,
                "read_only",
                self.object.hedge_data.id,
            ],
        )
        plantation_url = update_qs(plantation_url, {"source": "consultation"})
        context["plantation_url"] = plantation_url

        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(
            remove_mtm_params(current_url), {"mtm_campaign": "share-simu"}
        )

        parsed_moulinette_url = urlparse(self.object.moulinette_url)
        moulinette_params = parse_qs(parsed_moulinette_url.query)
        form_url = reverse("moulinette_form")

        moulinette_params["alternative"] = True
        edit_url = update_qs(form_url, moulinette_params)

        context["share_btn_url"] = share_btn_url
        context["edit_url"] = edit_url
        context["ds_url"] = self.object.demarches_simplifiees_petitioner_url
        context["triage_form"] = self.object.get_triage_form()

        matomo_custom_path = self.request.path.replace(
            self.object.reference, "+ref_projet+"
        )
        context["matomo_custom_url"] = update_url_with_matomo_params(
            self.request.build_absolute_uri(matomo_custom_path), self.request
        )
        context = {**context, **moulinette.get_extra_context(self.request)}

        return context


class PetitionProjectAutoRedirection(View):
    def get(self, request, *args, **kwargs):
        # Set a flag in the session
        request.session["auto_redirection"] = True
        # Redirect to the petition_project view
        return redirect(reverse("petition_project", kwargs=kwargs))


class PetitionProjectInstructorMixin(SingleObjectMixin):
    """Mixin for petition project instructor views"""

    slug_field = "reference"
    slug_url_kwarg = "reference"
    event_category = "dossier"
    event_action = None
    context_object_name = "petition_project"

    def has_view_permission(self, request, object):
        """Check if request has view permission on object"""
        return object.has_view_permission(request.user)

    def has_change_permission(self, request, object):
        """Check if request has edit permission on object"""
        return object.has_change_permission(request.user)

    def get_queryset(self):
        current_user = self.request.user
        messagerie_access_qs = LatestMessagerieAccess.objects.filter(
            user=current_user
        ).filter(project=OuterRef("pk"))
        followers_qs = (
            User.objects.filter(is_superuser=False)
            .filter(is_instructor=True)
            .filter(followed_petition_projects=OuterRef("pk"))
            .filter(departments=OuterRef("department"))
        )

        queryset = (
            PetitionProject.objects.all()
            .prefetch_related(
                Prefetch(
                    "status_history",
                    queryset=StatusLog.objects.all().order_by("-created_at"),
                )
            )
            .annotate(messagerie_access=Subquery(messagerie_access_qs.values("access")))
            .annotate(
                latest_access=Coalesce("messagerie_access", current_user.date_joined)
            )
            .annotate(followers=ArraySubquery(followers_qs.values("email")))
            .annotate(
                followed_up=Exists(
                    PetitionProject.followed_by.through.objects.filter(
                        petitionproject_id=OuterRef("pk"),
                        user_id=current_user.pk,
                    )
                ),
            )
        )
        return queryset

    def get_log_event_data(self):
        return self.object.get_log_event_data()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        moulinette = self.object.get_moulinette()
        context["moulinette"] = moulinette

        context.update(get_context_from_ds(self.object, moulinette))

        context.update(moulinette.catalog)

        context["plantation_evaluation"] = PlantationEvaluator(
            context["moulinette"], context["moulinette"].catalog["haies"]
        )

        plantation_url = reverse(
            "input_hedges",
            args=[
                moulinette.department.department,
                "read_only",
                self.object.hedge_data.id,
            ],
        )
        plantation_url = update_qs(plantation_url, {"source": "instruction"})
        context["plantation_url"] = plantation_url
        context["invitation_register_url"] = update_qs(
            self.request.build_absolute_uri(
                reverse(
                    "register",
                )
            ),
            {"mtm_campaign": INVITATION_TOKEN_MATOMO_TAG},
        )
        context["invitation_contact_url"] = update_qs(
            self.request.build_absolute_uri(
                reverse(
                    "contact_us",
                )
            ),
            {"mtm_campaign": INVITATION_TOKEN_MATOMO_TAG},
        )
        context["is_department_instructor"] = self.has_change_permission(
            self.request, self.object
        )

        matomo_custom_path = self.request.path.replace(
            self.object.reference, "+ref_projet+"
        )
        context["matomo_custom_url"] = update_url_with_matomo_params(
            self.request.build_absolute_uri(matomo_custom_path), self.request
        )
        context["ds_url"] = self.object.get_demarches_simplifiees_instructor_url(
            moulinette.config.demarche_simplifiee_number
        )

        # Send message if info from DS is not in project details
        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            messages.info(
                self.request,
                """L'accès à l'API démarches simplifiées n'est pas activée.
                Les données proviennent d'un dossier factice.""",
            )

        context["has_unread_messages"] = self.object.has_unread_messages

        return context


class BasePetitionProjectInstructorView(
    LoginRequiredMixin, PetitionProjectInstructorMixin, View
):
    """Base class for all instructor pages.

    - make sure the project is always available in the view.
    - make sure the permission is checked.
    - log read event (XXX why?)
    """

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.has_view_permission(request, self.object):
            return TemplateResponse(
                request=request, template="haie/petitions/403.html", status=403
            )
        res = super().get(request, *args, **kwargs)
        self.log_event_action(self.request)
        return res

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.has_change_permission(request, self.object):
            return TemplateResponse(
                request=request, template="haie/petitions/403.html", status=403
            )

        res = super().post(request, *args, **kwargs)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_change_permission"] = self.has_change_permission(
            self.request, self.object
        )
        return context

    def log_event_action(self, request):
        if not self.event_action:
            return

        referer = request.META.get("HTTP_REFERER")
        if (
            not referer
            or url_has_allowed_host_and_scheme(
                referer, allowed_hosts={request.get_host()}
            )
            and urlparse(referer).path != request.path
        ):
            # avoid logging event if user is just refreshing the page or is redirected after posting a form
            log_event(
                self.event_category,
                self.event_action,
                self.request,
                **self.get_log_event_data(),
                user_type=get_user_type(request.user),
                **get_matomo_tags(self.request),
            )


class PetitionProjectInstructorView(BasePetitionProjectInstructorView, DetailView):
    """View for petition project instructor page"""

    template_name = "haie/petitions/instructor_view.html"
    event_action = "consultation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_project_context(self.object, context["moulinette"]))
        return context

    def get_success_url(self):
        return reverse("petition_project_instructor_view", kwargs=self.kwargs)


class BasePetitionProjectInstructorUpdateView(
    BasePetitionProjectInstructorView, UpdateView
):
    """Base form view for petition project instructor pages"""

    form_class = PetitionProjectInstructorNotesForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not context["is_department_instructor"]:
            for field in context["form"].fields.values():
                field.widget.attrs["disabled"] = "disabled"
        return context


class PetitionProjectInstructorRegulationView(BasePetitionProjectInstructorUpdateView):
    """View for petition project instructor page"""

    template_name = "haie/petitions/instructor_view_regulation.html"

    def get_context_data(self, **kwargs):
        """Insert current regulation in context dict"""
        context = super().get_context_data(**kwargs)

        hedge_data = context["petition_project"].hedge_data
        context["ign_url"] = get_ign_centered_url(hedge_data)
        context["google_maps_url"] = get_google_maps_centered_url(hedge_data)

        regulation_slug = self.kwargs.get("regulation")
        regulation = context["moulinette"].get_regulation(regulation_slug)
        if regulation is None:
            raise Http404()

        context["regulation"] = regulation
        context["current_regulation"] = regulation
        return context

    def get_form_class(self):
        """Return the form class to use in this view."""
        regulation_slug = self.kwargs.get("regulation")
        if regulation_slug == "ep":
            return PetitionProjectInstructorEspecesProtegeesForm
        else:
            return self.form_class

    def get_success_url(self):
        return reverse(
            "petition_project_instructor_regulation_view", kwargs=self.kwargs
        )


class PetitionProjectInstructorDossierDSView(
    BasePetitionProjectInstructorView, DetailView
):
    """View for petition project page with demarches simplifiées data"""

    template_name = "haie/petitions/instructor_view_dossier_ds.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project_details = compute_instructor_informations_ds(
            self.object
        )  # compute DS details first as it will force update the dossier cache
        context["project_details"] = project_details
        # Send message if info from DS is not in project details
        if not context["project_details"]:
            messages.warning(
                self.request,
                """Impossible de récupérer les informations du dossier Démarches Simplifiées.
                Si le problème persiste, contactez le support en indiquant l'identifiant du dossier.""",
            )

        context["triage_form"] = self.object.get_triage_form()

        return context


class PetitionProjectInstructorNotesView(BasePetitionProjectInstructorUpdateView):
    """View for petition project instructor page"""

    template_name = "haie/petitions/instructor_view_notes.html"

    def form_valid(self, form):
        res = super().form_valid(form)
        log_event(
            "dossier",
            "edition_notes",
            self.request,
            reference=self.object.reference,
            **get_matomo_tags(self.request),
        )
        return res

    def get_success_url(self):
        return reverse("petition_project_instructor_notes_view", kwargs=self.kwargs)


class PetitionProjectInstructorMessagerieView(
    BasePetitionProjectInstructorView, FormView
):
    """View for petition project instructor page with demarche simplifiées messagerie"""

    template_name = "haie/petitions/instructor_view_dossier_messagerie.html"
    event_category = "message"
    event_action = "lecture"
    form_class = PetitionProjectInstructorMessageForm

    def get(self, request, *args, **kwargs):
        res = super().get(request, *args, **kwargs)

        # Invited instructors do not see the "unread message" notification pill
        # Hence, we only log messagerie accesses for instructors with edit permissions
        if res.status_code == 200 and self.has_change_permission(request, self.object):
            LatestMessagerieAccess.objects.update_or_create(
                user=request.user,
                project=self.object,
                defaults={"access": timezone.now()},
            )

        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ds_messages, ds_instructeurs_emails, ds_petitioner_email = (
            get_messages_and_senders_from_ds(self.object)
        )

        context["ds_messages"] = ds_messages
        context["ds_sender_emails_categories"] = {
            "petitioner": ds_petitioner_email,
            "instructor": ds_instructeurs_emails,
            "automatic": "contact@demarches-simplifiees.fr",
        }

        # Send message if info from DS is not in project details
        if context["ds_messages"] is None:
            messages.warning(
                self.request,
                """Impossible de récupérer les informations du dossier Démarches Simplifiées.
                Si le problème persiste, contactez le support en indiquant l'identifiant du dossier.""",
            )

        # Invited instructors cannot send messages
        context["has_send_message_permission"] = self.has_change_permission(
            self.request, self.object
        )

        return context

    def form_invalid(self, form):
        """Avoid errors if forms is invalid"""

        if form.errors:
            messages.warning(
                self.request,
                """Le message n’a pas pu être envoyé.
Vérifiez que la pièce jointe respecte les conditions suivantes :
<ul><li>Taille maximale : 20 Mo</li>
<li>Formats autorisés : PNG, JPG, PDF et ZIP</li>""",
            )

        self.object = self.get_object()
        return super().form_invalid(form)

    def form_valid(self, form):
        """Send message if form is valid"""
        message_body = form.cleaned_data["message_body"]
        attachments = form.cleaned_data["additional_file"]

        self.object = self.get_object()

        # Only instructors can send messages
        if not self.has_change_permission(self.request, self.object):
            return TemplateResponse(
                request=self.request, template="haie/petitions/403.html", status=403
            )

        ds_response = send_message_dossier_ds(self.object, message_body, attachments)
        self.event_action = "envoi"

        if ds_response is None or (
            "errors" in ds_response and ds_response["errors"] is not None
        ):
            messages.warning(
                self.request,
                """Le message n'a pas pu être envoyé, réessayez dans quelques minutes.
                Si le problème persiste, contactez le support en indiquant l'identifiant du dossier.""",
            )

        elif "message" in ds_response and ds_response["message"] is not None:
            messages.success(
                self.request,
                """Le message a bien été envoyé au demandeur.""",
            )

            # Log matomo event
            log_event(
                self.event_category,
                "envoi",
                self.request,
                reference=self.object.reference,
                piece_jointe=(
                    len(attachments)
                    if isinstance(attachments, list)
                    else 1 if attachments else 0
                ),
                **get_matomo_tags(self.request),
            )

        return super().form_valid(form)

    def get_log_event_data(self):
        return {
            "reference": self.object.reference,
        }

    def get_success_url(self):
        return reverse(
            "petition_project_instructor_messagerie_view", kwargs=self.kwargs
        )


class PetitionProjectInstructorMessagerieMarkUnreadView(
    BasePetitionProjectInstructorView, View
):
    """View for petition project instructor page with demarche simplifiées messagerie"""

    event_category = "message"
    event_action = "marquage_non_lu"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.has_change_permission(request, self.object):
            old_date = datetime.datetime(1985, 10, 1, tzinfo=datetime.UTC)
            LatestMessagerieAccess.objects.filter(
                project=self.object, user=request.user
            ).update(access=old_date)

            self.log_event_action(self.request)

        url = reverse("petition_project_instructor_view", args=[self.object.reference])
        return HttpResponseRedirect(url)


class PetitionProjectInstructorConsultationsView(
    BasePetitionProjectInstructorView, DetailView
):
    """View for managing invitation tokens (consultations)"""

    template_name = "haie/petitions/instructor_view_consultations.html"
    event_action = None  # do not log event

    def has_view_permission(self, request, object):
        """Only department administratons can see this page"""
        return object.has_change_permission(request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get only accepted tokens (those with a user)
        tokens = (
            InvitationToken.objects.filter(
                petition_project=self.object, user__isnull=False
            )
            .select_related("user")
            .order_by("-created_at")
        )

        context["public_url"] = self.request.build_absolute_uri(
            reverse("petition_project", args=[self.object.reference])
        )
        context["invitation_tokens"] = tokens
        context["invitation_token_create_url"] = self.request.build_absolute_uri(
            reverse(
                "petition_project_invitation_token_create",
                kwargs={"reference": self.object.reference},
            )
        )

        return context


class PetitionProjectInstructorAlternativeView(
    BasePetitionProjectInstructorView, FormView
):
    """View for creating an alternative of a petition project by the instructor"""

    template_name = "haie/petitions/instructor_view_alternatives.html"
    form_class = SimulationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["simulations"] = (
            Simulation.objects.filter(project=self.object)
            .select_related("project")
            .prefetch_related(
                Prefetch(
                    "project__status_history",
                    queryset=StatusLog.objects.all().order_by("-created_at"),
                )
            )
            .order_by("-created_at")
        )

        context["base_url"] = f"https://{settings.ENVERGO_HAIE_DOMAIN}"

        return context

    def form_valid(self, form):
        simulation = form.save(commit=False)
        simulation.project = self.object
        simulation.save()

        messages.success(self.request, "La simulation alternative a été ajoutée.")

        log_event(
            "dossier",
            "simulation_alt",
            self.request,
            action="add",
            **self.object.get_log_event_data(),
            **get_matomo_tags(self.request),
        )

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = reverse(
            "petition_project_instructor_alternative_view", args=[self.object.reference]
        )
        return url


class PetitionProjectInstructorAlternativeEdit(
    BasePetitionProjectInstructorView, FormView
):
    """View for updating alternative simulations."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.has_change_permission(request, self.object):
            return TemplateResponse(
                request=request, template="haie/petitions/403.html", status=403
            )

        simulation_qs = (
            Simulation.objects.filter(project=self.object)
            .select_related("project")
            .prefetch_related(
                Prefetch(
                    "project__status_history",
                    queryset=StatusLog.objects.all().order_by("-created_at"),
                )
            )
        )

        try:
            simulation = simulation_qs.get(pk=kwargs["simulation_id"])
        except Simulation.DoesNotExist:
            raise Http404()

        action = kwargs["action"]
        if action == "activate" and simulation.can_be_activated():
            with transaction.atomic():
                simulation_qs.update(is_active=False)
                simulation.is_active = True
                simulation.save()

                project = simulation.project
                project.moulinette_url = simulation.moulinette_url
                url = MoulinetteUrl(project.moulinette_url)
                project.hedge_data_id = url["haies"]
                project.save()

                messages.success(request, "La simulation alternative a été activée.")

                log_event(
                    "dossier",
                    "simulation_alt",
                    self.request,
                    action="activate",
                    **self.object.get_log_event_data(),
                    **get_matomo_tags(self.request),
                )

        # The main active simulation cannot be deleted
        elif action == "delete" and simulation.can_be_deleted():
            simulation.delete()

            messages.success(request, "La simulation alternative a été supprimée.")

            log_event(
                "dossier",
                "simulation_alt",
                self.request,
                action="delete",
                **self.object.get_log_event_data(),
                **get_matomo_tags(self.request),
            )

        else:
            # This should not happen unless someone manually forges an invalid URL
            return HttpResponseForbidden("Action non disponible")

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = reverse(
            "petition_project_instructor_alternative_view", args=[self.object.reference]
        )
        return url


class PetitionProjectInstructorProcedureView(
    BasePetitionProjectInstructorView, MultipleObjectMixin, FormView
):
    """View for display and edit the petition project procedure by the instructor"""

    form_class = ProcedureForm
    template_name = "haie/petitions/instructor_view_procedure.html"
    paginate_by = 10

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object_list = self.object.status_history.select_related(
            "created_by"
        ).order_by("-created_at")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object_list = self.object.status_history.select_related(
            "created_by"
        ).order_by("-created_at")
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["stage"] = self.object.stage
        initial["decision"] = self.object.decision

        return initial

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context.update(
            {
                "STAGES": STAGES,
                "DECISIONS": DECISIONS,
            }
        )

        # Request for additional information is only relevant when the project is
        # in the "instruction" phase
        if self.has_change_permission(
            self.request, self.object
        ) and self.object.stage.startswith("instruction"):
            request_info_form = RequestAdditionalInfoForm()
            resume_processing_form = ResumeProcessingForm()
            context.update(
                {
                    "request_info_form": request_info_form,
                    "resume_processing_form": resume_processing_form,
                }
            )

        return context

    def form_valid(self, form):

        def notify_admin():
            haie_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
            admin_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.object.pk],
            )
            procedure_url = reverse(
                "petition_project_instructor_procedure_view",
                kwargs={"reference": self.object.reference},
            )
            message = render_to_string(
                "haie/petitions/mattermost_project_procedure_edition.txt",
                context={
                    "department": self.object.department,
                    "reference": self.object.reference,
                    "admin_url": f"https://{haie_site.domain}{admin_url}",
                    "procedure_url": f"https://{haie_site.domain}{procedure_url}",
                },
            )
            notify(message, "haie")

        if self.object.is_additional_information_requested:
            form.add_error(
                None,
                ValidationError(
                    "Impossible de mofidier l'état du dossier tant qu'il est en attente de compléments.",
                    code="modification_while_paused",
                ),
            )
            return self.form_invalid(form)

        log = form.save(commit=False)
        log.petition_project = self.object
        log.created_by = self.request.user
        previous_stage = self.object.stage
        previous_decision = self.object.decision

        previous_ds_status = self.object.demarches_simplifiees_state
        new_ds_status = DEMARCHES_SIMPLIFIEES_STATUS_MAPPING[(log.stage, log.decision)]
        if previous_ds_status != new_ds_status:
            try:
                update_demarches_simplifiees_status(self.object, new_ds_status)
            except DemarchesSimplifieesError as e:
                logger.error(e)
                form.add_error(
                    None,
                    mark_safe(
                        f"""Impossible de mettre à jour le dossier dans Démarches Simplifiées. Si le problème persiste,
                        <a href='{reverse("contact_us")}'>contactez l'équipe du Guichet Unique de la Haie</a> en
                        indiquant l'identifiant du dossier."""
                    ),
                )
                return self.form_invalid(form)

        log.save()

        res = HttpResponseRedirect(self.get_success_url())

        transaction.on_commit(
            lambda: log_event(
                "dossier",
                "modification_etat",
                self.request,
                reference=self.object.reference,
                etape_i=previous_stage,
                department=self.object.get_department_code(),
                etape_f=log.stage,
                decision_i=previous_decision,
                decision_f=log.decision,
                **get_matomo_tags(self.request),
            )
        )
        transaction.on_commit(notify_admin)

        return res

    def get_success_url(self):
        return reverse("petition_project_instructor_procedure_view", kwargs=self.kwargs)


class PetitionProjectInstructorRequestAdditionalInfoView(
    BasePetitionProjectInstructorView, FormView
):
    """Process the "request additional info / resume instruction" forms."""

    http_method_names = ["post"]

    def get_form_class(self):
        if self.object.is_additional_information_requested:
            form_class = ResumeProcessingForm
        else:
            form_class = RequestAdditionalInfoForm
        return form_class

    def form_invalid(self, form):
        messages.error(self.request, "L'état du dossier n'a pas pu être mis à jour.")

        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        if isinstance(form, ResumeProcessingForm):
            return self.resume_form_valid(form)
        else:
            return self.pause_form_valid(form)

    def pause_form_valid(self, form):
        """Instructor requested additional data."""

        project = self.object

        try:
            with transaction.atomic():
                # Create a new suspension log entry
                StatusLog.objects.create(
                    petition_project=project,
                    type=LOG_TYPES.suspension,
                    due_date=form.cleaned_data["due_date"],
                    original_due_date=project.due_date,
                    created_by=self.request.user,
                    update_comment="Suspension de l’instruction, message envoyé au demandeur.",
                )

                # Send DS Message
                message = form.cleaned_data["request_message"]
                ds_response = send_message_dossier_ds(self.object, message)

                if ds_response is None or ds_response.get("errors") is not None:
                    if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
                        messages.info(
                            self.request,
                            """L'accès à l'API démarches simplifiées n'est pas activée.
                            Le message n'est pas envoyé""",
                        )
                    else:
                        # We raise an exception to make sure the data model transaction
                        # is aborted
                        raise DemarchesSimplifieesError(message="DS message not sent")

            # Send Mattermost notification
            haie_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
            admin_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.object.pk],
            )
            procedure_url = reverse(
                "petition_project_instructor_procedure_view",
                kwargs={"reference": self.object.reference},
            )
            messagerie_url = reverse(
                "petition_project_instructor_messagerie_view",
                args=[project.reference],
            )
            message = render_to_string(
                "haie/petitions/mattermost_project_request_additional_info.txt",
                context={
                    "department": self.object.department,
                    "reference": self.object.reference,
                    "admin_url": f"https://{haie_site.domain}{admin_url}",
                    "procedure_url": f"https://{haie_site.domain}{procedure_url}",
                    "messagerie_url": f"https://{haie_site.domain}{messagerie_url}",
                },
            )
            notify(message, "haie")

            # Log analytics event
            log_event(
                "dossier",
                "suspension_delai",
                self.request,
                switch="on",
                **project.get_log_event_data(),
                **get_matomo_tags(self.request),
            )

            success_message = f"""
            Le message au demandeur a bien été envoyé.
            <a href="{messagerie_url}">Retrouvez-le dans la messagerie.</a>
            """
            messages.success(self.request, success_message)
            res = HttpResponseRedirect(self.get_success_url())
            return res

        except DemarchesSimplifieesError:
            error_message = """Le message n'a pas pu être envoyé.
            Merci de ré-essayer dans quelques minutes.
            Si le problème persiste, contacter le support en indiquant l'identifiant du dossier.
            """
            messages.error(self.request, error_message)
            res = HttpResponseRedirect(self.get_success_url())
            return res

    def resume_form_valid(self, form):
        """Instructor received the requested additional info."""

        project = self.object
        suspension = project.latest_suspension

        # Compute the new due date, that is the original due date + number of interruption days
        # Note: if you modify this rule, you must apply the same update in the sync_new_due_date.js file
        info_receipt_date = form.cleaned_data["info_receipt_date"]
        interruption_days = info_receipt_date - suspension.created_at.date()
        if suspension.original_due_date:
            new_due_date = suspension.original_due_date + interruption_days
        else:
            new_due_date = None

        # Create a new resumption log entry
        StatusLog.objects.create(
            petition_project=project,
            type=LOG_TYPES.resumption,
            info_receipt_date=info_receipt_date,
            due_date=new_due_date,
            created_by=self.request.user,
            update_comment=(
                "Reprise de l’instruction, date d'échéance ajustée."
                if new_due_date
                else "Reprise de l’instruction."
            ),
        )

        # Send Mattermost notification
        haie_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        admin_url = reverse(
            "admin:petitions_petitionproject_change",
            args=[self.object.pk],
        )
        procedure_url = reverse(
            "petition_project_instructor_procedure_view",
            kwargs={"reference": self.object.reference},
        )
        message = render_to_string(
            "haie/petitions/mattermost_project_resume_instruction.txt",
            context={
                "department": self.object.department,
                "reference": self.object.reference,
                "admin_url": f"https://{haie_site.domain}{admin_url}",
                "procedure_url": f"https://{haie_site.domain}{procedure_url}",
            },
        )
        notify(message, "haie")

        # Log analytics event
        log_event(
            "dossier",
            "suspension_delai",
            self.request,
            switch="off",
            **project.get_log_event_data(),
            **get_matomo_tags(self.request),
        )

        success_message = "L'instruction du dossier a repris."
        messages.success(self.request, success_message)
        res = HttpResponseRedirect(self.get_success_url())
        return res

    def get_success_url(self):
        project = self.get_object()
        url = reverse(
            "petition_project_instructor_procedure_view", args=[project.reference]
        )
        return url


class PetitionProjectHedgeDataExport(DetailView):
    """Export Hedge data in geopackage"""

    model = PetitionProject
    slug_field = "reference"
    slug_url_kwarg = "reference"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        data = self.object.hedge_data

        with tempfile.TemporaryDirectory() as tmpdirname:
            template_file = settings.GUH_DATA_EXPORT_TEMPLATE
            export_file = os.path.join(tmpdirname, "output.gpkg")
            shutil.copy(template_file, export_file)

            # Fiona cannot append to an existing file
            # By opening a layer in write mode, it will squash the layer data
            # Luckily for us, that's the behaviour we want
            with fiona.open(template_file) as src, fiona.open(
                export_file, "w", layer="haies", **src.meta
            ) as dst:
                for hedge in data.hedges():
                    transformer = Transformer.from_crs(
                        EPSG_WGS84, EPSG_LAMB93, always_xy=True
                    )
                    geometry = Geometry.from_dict(
                        transform(transformer.transform, hedge.geometry)
                    )
                    properties = Properties.from_dict(
                        {
                            "id": hedge.id,
                            "type": (
                                "A_PLANTER" if hedge.type == TO_PLANT else "A_DETRUIRE"
                            ),
                            "type_haie": hedge.hedge_type,
                            "sur_parcelle_pac": "oui" if hedge.is_on_pac else "non",
                        }
                    )
                    feat = Feature(geometry=geometry, properties=properties)
                    dst.write(feat)

            # Create a response with the GeoPackage file
            export_filename = "haies_dossier.gpkg"
            if self.object.demarches_simplifiees_dossier_number:
                export_filename = f"haies_dossier_{self.object.demarches_simplifiees_dossier_number}.gpkg"

            with open(export_file, "rb") as f:
                response = HttpResponse(f.read(), content_type="application/geopackage")
                response["Content-Disposition"] = (
                    f'attachment; filename="{export_filename}"'
                )

        return response


class PetitionProjectInvitationTokenCreate(BasePetitionProjectInstructorView):
    """Create an invitation token and return modal HTML with the invitation content"""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):

        # We don't call super() because we only inherit frow `View`, which does not
        # have a `post` method
        self.object = self.get_object()
        if not self.has_change_permission(request, self.object):
            return TemplateResponse(
                request=request, template="haie/petitions/403.html", status=403
            )

        project = self.object
        token = InvitationToken.objects.create(
            created_by=request.user,
            petition_project=project,
        )
        url = reverse("petition_project_instructor_view", args=[project.reference])
        invitation_url = update_qs(
            self.request.build_absolute_uri(url),
            {
                "mtm_campaign": INVITATION_TOKEN_MATOMO_TAG,
                "invitation_token": token.token,
            },
        )
        log_event(
            "dossier",
            "invitation_creation",
            self.request,
            reference=project.reference,
            department=project.get_department_code(),
            **get_matomo_tags(self.request),
        )
        # Return rendered modal HTML instead of JSON
        invitation_contact_url = update_qs(
            self.request.build_absolute_uri(
                reverse(
                    "contact_us",
                )
            ),
            {"mtm_campaign": INVITATION_TOKEN_MATOMO_TAG},
        )
        return TemplateResponse(
            request=request,
            template="haie/petitions/_invitation_token_modal_content.html",
            context={
                "invitation_url": invitation_url,
                "invitation_contact_url": invitation_contact_url,
            },
        )


class PetitionProjectInvitationTokenDelete(BasePetitionProjectInstructorView):
    """Delete (revoke) an invitation token"""

    http_method_names = ["post"]

    def get_success_url(self):
        return reverse(
            "petition_project_instructor_consultations_view",
            kwargs={"reference": self.object.reference},
        )

    def post(self, request, *args, **kwargs):

        # We don't call super() because we only inherit from `View`, which does not
        # have a `post` method
        self.object = self.get_object()
        if not self.has_change_permission(request, self.object):
            return HttpResponseForbidden(
                "Vous n'avez pas la permission de révoquer une invitation"
            )

        project = self.object
        token_id = request.POST.get("token_id")
        if not token_id:
            return HttpResponseBadRequest("Identifiant de token manquant.")

        try:
            token = InvitationToken.objects.get(id=token_id, petition_project=project)
        except InvitationToken.DoesNotExist:
            return HttpResponseNotFound("Invitation non trouvée")

        token.delete()
        log_event(
            "dossier",
            "invitation_revocation",
            self.request,
            reference=project.reference,
            department=project.get_department_code(),
            **get_matomo_tags(self.request),
        )

        messages.success(request, "L'accès a été révoqué avec succès.")
        return redirect(self.get_success_url())


class PetitionProjectAcceptInvitation(RedirectView):
    """Accept an invitation to a petition project.

    This is a legacy view that was responsible for accepting invitations. It is now
    obsolete so it was changed to a simple redirection so as to not break existing
    tokens.

    """

    # Regex for tokens generated by secrets.token_urlsafe(32)
    # 32 bytes encoded in URL-safe base64 = 43 characters (A-Z, a-z, 0-9, -, _)
    # We validate the token to prevent phishing attempts, since we use a user-provided
    # value to build the redirection url
    TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")

    def get_redirect_url(self, *args, **kwargs):
        reference = kwargs.get("reference")
        token = kwargs.get("token")

        if not token or not self.TOKEN_PATTERN.match(token):
            raise SuspiciousOperation("Invalid invitation token format")

        url = reverse("petition_project_instructor_view", args=[reference])
        url_with_token = f"{url}?{settings.INVITATION_TOKEN_COOKIE_NAME}={token}"
        return url_with_token


@login_required
@require_POST
def toggle_follow_project(request, reference):
    """Toggle follow/unfollow a petition project"""
    project = get_object_or_404(PetitionProject, reference=reference)
    if not project.has_view_permission(request.user):
        return TemplateResponse(
            request=request, template="haie/petitions/403.html", status=403
        )

    if request.POST.get("follow") == "true":
        project.followed_by.add(request.user)
        switch = "on"
    else:
        project.followed_by.remove(request.user)
        switch = "off"

    # Get the next URL from POST or referrer
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"

    log_event(
        "dossier",
        "suivi",
        request,
        reference=project.reference,
        switch=switch,
        view=(
            "liste"
            if "liste" in next_url
            else "detail" if "instruction" in next_url else next_url
        ),
        **get_matomo_tags(request),
    )

    # Ensure the URL is safe (avoid open redirects)
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = settings.LOGIN_REDIRECT_URL  # or "/" as a safe fallback

    return redirect(next_url)
