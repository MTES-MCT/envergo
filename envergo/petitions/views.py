import logging
from textwrap import dedent
from typing import Any, List
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from envergo.analytics.utils import get_matomo_tags, log_event
from envergo.moulinette.models import (
    ConfigHaie,
    MoulinetteHaie,
    get_moulinette_class_from_site,
)
from envergo.moulinette.views import MoulinetteMixin
from envergo.petitions.forms import PetitionProjectForm
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify
from envergo.utils.tools import display_form_details, generate_key
from envergo.utils.urls import extract_param_from_url

logger = logging.getLogger(__name__)


class PetitionProjectCreate(FormView):
    form_class = PetitionProjectForm

    def dispatch(self, request, *args, **kwargs):
        # store alerts in the request object to notify admins if needed
        request.alerts = AlertList(request)
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
                Alert("missing_demarche_simplifiee_number", is_fatal=True)
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
                    Alert(
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
                Alert(
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
                    Alert(
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
                    Alert(
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
                    Alert(
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
                    Alert(
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
            self.request.alerts.append(Alert("invalid_form", is_fatal=True))

        if len(self.request.alerts) == 0:
            self.request.alerts.append(Alert("unknown_error", is_fatal=True))

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


class PetitionProjectDetail(MoulinetteMixin, FormView):
    template_name = "haie/moulinette/result_plantation.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.moulinette = None

    def get(self, request, *args, **kwargs):

        # Instanciate the moulinette object from the petition project in order to use the MoulinetteMixin
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

        # Log the consultation event only if it is not after an automatic redirection due to dossier creation
        if not request.session.pop("auto_redirection", False):
            log_event(
                "projet",
                "consultation",
                self.request,
                **petition_project.get_log_event_data(),
                **get_matomo_tags(self.request),
            )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["moulinette"] = self.moulinette
        context["base_result"] = self.moulinette.get_result_template()
        context["is_read_only"] = True
        return context


class PetitionProjectAutoRedirection(View):
    def get(self, request, *args, **kwargs):
        # Set a flag in the session
        request.session["auto_redirection"] = True
        # Redirect to the petition_project view
        return redirect(reverse("petition_project", kwargs=kwargs))


class Alert:
    def __init__(self, key, extra: dict[str, Any] = dict, is_fatal=False):
        self.key = key
        self.extra = extra
        self.is_fatal = is_fatal


class AlertList(List[Alert]):
    def __init__(self, request):
        super().__init__()
        self.request = request
        self._config = None
        self._petition_project = None
        self._form = None
        self._user_error_reference = None

    @property
    def petition_project(self):
        return self._petition_project

    @petition_project.setter
    def petition_project(self, value):
        self._petition_project = value

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @property
    def form(self):
        return self._form

    @form.setter
    def form(self, value):
        self._form = value

    @property
    def user_error_reference(self):
        return self._user_error_reference

    @user_error_reference.setter
    def user_error_reference(self, value):
        self._user_error_reference = value

    def append(self, item: Alert) -> None:
        if not isinstance(item, Alert):
            raise TypeError("Only Alert instances can be added to AlertList")
        super().append(item)

    def compute_message(self):
        lines = []
        config_url = None
        if self.config:
            config_relative_url = reverse(
                "admin:moulinette_confighaie_change", args=[self.config.id]
            )
            config_url = self.request.build_absolute_uri(config_relative_url)

        if self.petition_project:
            lines.append("#### Mapping avec Démarches-simplifiées : :warning: anomalie")
            projet_relative_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.petition_project.id],
            )
            projet_url = self.request.build_absolute_uri(projet_relative_url)

            lines.append("Un dossier a été créé sur démarches-simplifiées : ")
            lines.append(f"* [projet dans l’admin]({projet_url})")

            if self.config:
                dossier_url = (
                    f"https://www.demarches-simplifiees.fr/procedures/"
                    f"{self.config.demarche_simplifiee_number}/dossiers/"
                    f"{self.petition_project.demarches_simplifiees_dossier_number}"
                )
                lines.append(
                    f"* [dossier DS n°{self.petition_project.demarches_simplifiees_dossier_number}]"
                    f"({dossier_url}) (:icon-info:  le lien ne sera fonctionnel qu’après le dépôt du dossier"
                    f" par le pétitionnaire)"
                )
            if config_url:
                lines.append("")
                lines.append(
                    f"Une ou plusieurs anomalies ont été détectées dans la [configuration du département "
                    f"{self.config.department}]({config_url})"
                )

            lines.append("")
            lines.append(
                "Le dossier a été créé sans encombres, mais il contient peut-être des réponses sans pré-remplissage "
                "ou avec une valeur erronnée."
            )

        else:
            lines.append("### Mapping avec Démarches-simplifiées : :x: erreur")

            lines.append(
                "La création d’un dossier démarches-simplifiées n’a pas pu aboutir."
            )

            if config_url:
                lines.append(
                    f"Cette erreur révèle une possible anomalie de la [configuration du département "
                    f"{self.config.department}]({config_url})"
                )

            lines.append(
                f"L’utilisateur a reçu un message d’erreur avec l’identifiant `{self.user_error_reference.upper()}` "
                f"l’invitant à nous contacter."
            )

            if self.form:
                lines.append(
                    f"""
* form :
```
{display_form_details(self.form)}
```
"""
                )

        index = 0

        for alert in self:
            index = index + 1
            if alert.is_fatal:
                lines.append("")
                lines.append(f"#### :x: Description de l’erreur #{index}")
            else:
                lines.append("")
                lines.append(f"#### :warning: Description de l’anomalie #{index}")

            if alert.key == "missing_demarche_simplifiee_number":
                lines.append(
                    "Un département activé doit toujours avoir un numéro de démarche sur Démarches Simplifiées"
                )

            elif alert.key == "invalid_prefill_field":
                lines.append(
                    "Chaque entrée de la configuration de pré-remplissage doit obligatoirement avoir un id et une "
                    "valeur. Le mapping est optionnel."
                )
                lines.append(f"* Champ : {alert.extra['field']}")

            elif alert.key == "ds_api_http_error":
                lines.append(
                    "L'API de Démarches Simplifiées a retourné une erreur lors de la création du dossier."
                )
                lines.append(
                    dedent(
                        f"""
                **Requête:**
                * url : {alert.extra['api_url']}
                * body :
                ```
                {alert.extra['request_body']}
                ```

                **Réponse:**
                * status : {alert.extra['response'].status_code}
                * content:
                ```
                {alert.extra['response'].text}
                ```
                """
                    )
                )

            elif alert.key == "missing_source_regulation":
                lines.append(
                    f"La configuration demande de pré-remplir un champ avec la valeur de **{alert.extra['source']}** "
                    f"mais la moulinette n'a pas de résultat pour la réglementation "
                    f"**{alert.extra['regulation_slug']}**."
                )

            elif alert.key == "missing_source_criterion":
                lines.append(
                    f"La configuration demande de pré-remplir un champ avec la valeur de **{alert.extra['source']}** "
                    f"mais la moulinette n'a pas de résultat pour le critère "
                    f"**{alert.extra['criterion_slug']}**."
                )

            elif alert.key == "missing_source_moulinette":
                lines.append(
                    f"La configuration demande de pré-remplir un champ avec la valeur de **{alert.extra['source']}** "
                    f"mais la simulation ne possède pas cette valeur."
                )

            elif alert.key == "mapping_missing_value":
                lines.append(
                    dedent(
                        f"""\
               Une valeur prise en entrée n’a pas été reconnue dans le mapping
               * Champ : {alert.extra['source']}
               * Valeur : {alert.extra['value']}
               * mapping :
               ```
               {alert.extra['mapping']}
               ```
               """
                    )
                )

            elif alert.key == "invalid_form":
                lines.append("Le formulaire contient des erreurs")

            elif alert.key == "unknown_error":
                lines.append("Nous ne savons pas d'où provient ce problème...")

            else:
                logger.error(
                    "Unknown alert key during petition project creation",
                    extra={"alert": alert},
                )

        return "\n".join(lines)
