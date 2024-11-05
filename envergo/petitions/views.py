import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.http import JsonResponse, QueryDict
from django.urls import reverse
from django.views.generic import FormView

from envergo.moulinette.models import get_moulinette_class_from_site
from envergo.moulinette.views import MoulinetteMixin
from envergo.petitions.forms import PetitionProjectForm
from envergo.petitions.models import PetitionProject

logger = logging.getLogger(__name__)


class PetitionProjectCreate(FormView):
    form_class = PetitionProjectForm

    def form_valid(self, form):
        moulinette_url = form.cleaned_data["moulinette_url"]
        profil = form.cleaned_data["profil"]

        form.instance.hedges_data = form.cleaned_data["haies"].data
        petition_project = form.save()

        # At petition project creation, we also create a pre-filled dossier on demarches-simplifiees.fr
        read_only_url = reverse(
            "petition_project",
            kwargs={"reference": petition_project.reference},
        )
        # Ce code est particulièrement fragile.
        # Un changement dans un label côté démarche simplifiées cassera ce mapping sans prévenir.
        mapping_demarche_simplifiee = {
            "autre": "Autre (collectivité, aménageur, gestionnaire de réseau, particulier, etc.)",
            "agri_pac": "Exploitant-e agricole bénéficiaire de la PAC",
        }
        demarche_id = settings.DEMARCHES_SIMPLIFIEE["DEMARCHE_HAIE"]["ID"]
        api_url = f"{settings.DEMARCHES_SIMPLIFIEE['API_URL']}demarches/{demarche_id}/dossiers"

        body = {
            settings.DEMARCHES_SIMPLIFIEE["DEMARCHE_HAIE"][
                "PROFIL_FIELD_ID"
            ]: mapping_demarche_simplifiee[profil],
            settings.DEMARCHES_SIMPLIFIEE["DEMARCHE_HAIE"][
                "MOULINETTE_URL_FIELD_ID"
            ]: moulinette_url,
        }

        response = requests.post(
            api_url, json=body, headers={"Content-Type": "application/json"}
        )
        demarche_simplifiee_url = None

        if 200 <= response.status_code < 400:
            data = response.json()
            demarche_simplifiee_url = data.get("dossier_url")
        else:
            logger.error(
                "Error while pre-filling a dossier on demarches-simplifiees.fr",
                extra={"response": response},
            )

        if not demarche_simplifiee_url:
            res = self.form_invalid(form)
        else:
            res = JsonResponse(
                {
                    "demarche_simplifiee_url": demarche_simplifiee_url,
                    "read_only_url": read_only_url,
                }
            )

        return res

    def form_invalid(self, form):
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
        petition_project = PetitionProject.objects.get(
            reference=self.kwargs["reference"]
        )
        parsed_url = urlparse(petition_project.moulinette_url)
        query_string = parsed_url.query
        # We need to convert the query string to a flat dict
        moulinette_data = {
            key: value[0] if isinstance(value, list) and len(value) <= 1 else value
            for key, value in QueryDict(query_string).items()
        }
        MoulinetteClass = get_moulinette_class_from_site(self.request.site)
        self.moulinette = MoulinetteClass(
            moulinette_data, moulinette_data, self.should_activate_optional_criteria()
        )
        # Save the moulinette data in the request object
        # we will need it for things like triage form or params validation
        self.request.moulinette_data = moulinette_data

        if self.moulinette.has_missing_data():
            raise NotImplementedError("We do not handle uncompleted project yet")

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
