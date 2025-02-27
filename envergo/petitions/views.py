import logging
import os
import shutil
import tempfile
from urllib.parse import parse_qs, urlparse

import fiona
import requests
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, UpdateView
from fiona import Feature, Geometry, Properties
from pyproj import Transformer
from shapely.ops import transform

from envergo.analytics.utils import get_matomo_tags, log_event
from envergo.hedges.models import EPSG_LAMB93, EPSG_WGS84, TO_PLANT
from envergo.hedges.services import PlantationEvaluator
from envergo.moulinette.models import ConfigHaie, MoulinetteHaie
from envergo.petitions.forms import PetitionProjectForm, PetitionProjectInstructorForm
from envergo.petitions.models import PetitionProject
from envergo.petitions.services import (
    PetitionProjectCreationAlert,
    PetitionProjectCreationProblem,
    compute_instructor_informations,
)
from envergo.utils.mattermost import notify
from envergo.utils.tools import generate_key
from envergo.utils.urls import extract_param_from_url, update_qs

logger = logging.getLogger(__name__)


class PetitionProjectCreate(FormView):
    form_class = PetitionProjectForm

    def dispatch(self, request, *args, **kwargs):
        # store alerts in the request object to notify admins if needed
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

                log_event(
                    "dossier",
                    "creation",
                    self.request,
                    **petition_project.get_log_event_data(),
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

        api_url = f"{settings.DEMARCHES_SIMPLIFIEE['PRE_FILL_API_URL']}demarches/{demarche_id}/dossiers"
        body = {}
        moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
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
        elif source == "vieil_arbre":
            haies = moulinette.catalog.get("haies")
            if haies:
                value = haies.is_removing_old_tree()
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
                "projet",
                "consultation",
                self.request,
                **self.object.get_log_event_data(),
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
        context["base_result"] = moulinette.get_result_template()
        context["is_read_only"] = True
        context["plantation_evaluation"] = PlantationEvaluator(
            moulinette, moulinette.catalog["haies"]
        )
        context["demarches_simplifiees_dossier_number"] = (
            self.object.demarches_simplifiees_dossier_number
        )
        context["created_at"] = self.object.created_at

        parsed_moulinette_url = urlparse(self.object.moulinette_url)
        moulinette_params = parse_qs(parsed_moulinette_url.query)
        moulinette_params["edit"] = ["true"]
        result_url = reverse("moulinette_result")
        edit_url = update_qs(result_url, moulinette_params)

        context["edit_url"] = edit_url
        context["ds_url"] = (
            f"https://www.demarches-simplifiees.fr/dossiers/"
            f"{self.object.demarches_simplifiees_dossier_number}"
        )
        return context


class PetitionProjectAutoRedirection(View):
    def get(self, request, *args, **kwargs):
        # Set a flag in the session
        request.session["auto_redirection"] = True
        # Redirect to the petition_project view
        return redirect(reverse("petition_project", kwargs=kwargs))


class PetitionProjectInstructorView(LoginRequiredMixin, UpdateView):
    template_name = "haie/petitions/instructor_view.html"
    queryset = PetitionProject.objects.all()
    slug_field = "reference"
    slug_url_kwarg = "reference"
    form_class = PetitionProjectInstructorForm

    def get(self, request, *args, **kwargs):
        result = super().get(request, *args, **kwargs)

        log_event(
            "projet",
            "consultation_i",
            self.request,
            **self.object.get_log_event_data(),
            **get_matomo_tags(self.request),
        )
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = self.object.get_moulinette()
        context["petition_project"] = self.object
        context["moulinette"] = moulinette
        context["project_url"] = reverse(
            "petition_project", kwargs={"reference": self.object.reference}
        )
        context["project_details"] = compute_instructor_informations(
            self.object, moulinette
        )

        return context

    def get_success_url(self):
        return reverse("petition_project_instructor_view", kwargs=self.kwargs)


class PetitionProjectHedgeDataExport(DetailView):
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
                export_file, "w", layer="haie_envergo", **src.meta
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
                                "A_PLANTER" if hedge.type == TO_PLANT else "A_ARRACHER"
                            ),
                            "typeHaie": hedge.hedge_type,
                            "vieilArbre": "oui" if hedge.vieil_arbre else "non",
                            "proximiteMare": ("oui" if hedge.proximite_mare else "non"),
                            "surParcellePac": "oui" if hedge.is_on_pac else "non",
                            "proximitePointEau": (
                                "oui" if hedge.proximite_point_eau else "non"
                            ),
                            "connexionBoisement": (
                                "oui" if hedge.connexion_boisement else "non"
                            ),
                            "sousLigneElectrique": (
                                "oui" if hedge.sous_ligne_electrique else "non"
                            ),
                            "proximiteVoirie": (
                                "oui" if hedge.proximite_voirie else "non"
                            ),
                        }
                    )
                    feat = Feature(geometry=geometry, properties=properties)
                    dst.write(feat)

            # Create a response with the GeoPackage file
            with open(export_file, "rb") as f:
                response = HttpResponse(f.read(), content_type="application/geopackage")
                response["Content-Disposition"] = (
                    'attachment; filename="guh_export.gpkg"'
                )

        return response
