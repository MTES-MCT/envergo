import logging
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from envergo.analytics.utils import log_event
from envergo.moulinette.models import (
    ConfigHaie,
    MoulinetteHaie,
    get_moulinette_class_from_site,
)
from envergo.moulinette.views import MoulinetteMixin
from envergo.petitions.forms import PetitionProjectForm
from envergo.petitions.models import PetitionProject
from envergo.utils.urls import extract_param_from_url

logger = logging.getLogger(__name__)


class PetitionProjectCreate(FormView):
    form_class = PetitionProjectForm

    def form_valid(self, form):
        form.instance.hedge_data_id = extract_param_from_url(
            form.cleaned_data["moulinette_url"], "haies"
        )

        with transaction.atomic():
            petition_project = form.save()
            read_only_url = reverse(
                "petition_project",
                kwargs={"reference": petition_project.reference},
            )

            demarche_simplifiee_url = self.pre_fill_demarche_simplifiee(
                petition_project
            )

            if not demarche_simplifiee_url:
                res = self.form_invalid(form)
                # Rollback the transaction to avoid saving the petition project
                transaction.set_rollback(True)
            else:
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
        config = ConfigHaie.objects.get(
            department__department=department
        )  # it should always exist, otherwise the simulator would not be available
        demarche_id = config.demarche_simplifiee_number

        if not demarche_id:
            logger.error(
                "An activated department should always have a demarche_simplifiee_number",
                extra={"haie config": config.id, "department": department},
            )
            return None

        api_url = f"{settings.DEMARCHES_SIMPLIFIEE['API_URL']}demarches/{demarche_id}/dossiers"
        body = {}
        moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
        for field in config.demarche_simplifiee_pre_fill_config:
            if "id" not in field or "value" not in field:
                logger.error(
                    "Invalid pre-fill configuration for a dossier on demarches-simplifiees.fr",
                    extra={"haie config": config.id, "field": field},
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
        redirect_url = None
        if 200 <= response.status_code < 400:
            data = response.json()
            redirect_url = data.get("dossier_url")
        else:
            logger.error(
                "Error while pre-filling a dossier on demarches-simplifiees.fr",
                extra={"response": response},
            )
        return redirect_url

    def get_value_from_source(
        self, petition_project, moulinette, source, mapping, config
    ):
        """Get the value to pre-fill a dossier on demarches-simplifiees.fr from a source.

        Available sources are listed by this method : ConfigHaie.get_demarche_simplifiee_value_sources()
        Depending on the source, the value comes from the moulinette data, the moulinette result or the moulinette url.
        Then it will map the value if a mapping is provided.
        """
        if source == "moulinette_url":
            value = petition_project.moulinette_url
        elif source == "project_url":
            value = self.request.build_absolute_uri(
                reverse(
                    "petition_project",
                    kwargs={"reference": petition_project.reference},
                )
            )
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
                value = None
            else:
                value = regulation_result.result
        else:
            value = moulinette.catalog.get(source, None)

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

        mapped_value = mapping.get(value, value)

        # Handle boolean values as strings 😞
        return {
            True: "true",
            False: "false",
        }.get(mapped_value, mapped_value)

    def form_invalid(self, form):
        logger.error("Unable to create a petition project", extra={"form": form.errors})
        return JsonResponse(
            {
                "error_title": "Un problème technique empêche la création de votre dossier.",
                "error_body": "Nous vous invitons à enregistrer votre simulation et à réessayer ultérieurement.",
            },
            status=400,
        )


class PetitionProjectDetail(MoulinetteMixin, FormView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.moulinette = None

    def get(self, request, *args, **kwargs):
        petition_project = get_object_or_404(
            PetitionProject.objects.select_related("hedge_data"),
            reference=self.kwargs["reference"],
        )
        parsed_url = urlparse(petition_project.moulinette_url)
        query_string = parsed_url.query
        # We need to convert the query string to a flat dict
        raw_data = QueryDict(query_string)
        # Save the moulinette data in the request object
        # we will need it for things like triage form or params validation
        self.request.moulinette_data = raw_data

        moulinette_data = raw_data.dict()
        moulinette_data["haies"] = petition_project.hedge_data

        MoulinetteClass = get_moulinette_class_from_site(self.request.site)
        self.moulinette = MoulinetteClass(
            moulinette_data,
            moulinette_data,
            self.should_activate_optional_criteria(),
        )

        if self.moulinette.has_missing_data():
            # this should not happen, unless we have stored an incomplete project
            # If we add some new regulations, or adding evaluators on existing ones, we could have obsolete moulinette
            # we should implement static simulation/project to avoid this case.
            logger.warning(
                "A petition project has missing data. This should not happen unless regulations have changed."
                "We should implement static simulation/project to avoid this case.",
                extra={"reference": petition_project.reference},
            )
            raise NotImplementedError("We do not handle uncompleted project")

        log_event(
            "projet",
            "consultation",
            self.request,
            **{
                "reference": petition_project.reference,
                "department": moulinette_data.get("department"),
                "longueur_detruite": moulinette_data["haies"].length_to_remove(),
                "longueur_plantee": moulinette_data["haies"].length_to_plant(),
            },
        )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["moulinette"] = self.moulinette
        context["base_result"] = self.moulinette.get_result_template()
        context["is_read_only"] = True
        return context

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""
        moulinette = self.moulinette
        return [moulinette.get_result_template()]
