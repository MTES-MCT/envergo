import logging
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, List, Literal
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.http import QueryDict
from django.urls import reverse

from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.models import MoulinetteHaie
from envergo.utils.mattermost import notify
from envergo.utils.tools import display_form_details

logger = logging.getLogger(__name__)


@dataclass
class AdditionalInfo:
    label: str
    value: str | int | float
    unit: str | None


@dataclass
class ItemDetails:
    result: bool
    details: list[AdditionalInfo]


@dataclass
class Item:
    label: str
    value: str | int | float | ItemDetails
    unit: str | None
    comment: str | None


@dataclass
class InstructorInformationDetails:
    label: str
    items: list[Item]


@dataclass
class InstructorInformation:
    slug: str | None
    label: str | None
    items: list[Item | Literal["instructor_free_mention", "onagre_number"]]
    details: list[InstructorInformationDetails]
    comment: str | None = None


@dataclass
class ProjectDetails:
    demarches_simplifiees_dossier_number: int
    demarche_simplifiee_number: int
    usager: str
    details: list[InstructorInformation]


def compute_instructor_informations(petition_project, moulinette) -> ProjectDetails:
    config = moulinette.config
    ds_details = fetch_project_details_from_demarches_simplifiees(
        petition_project.demarches_simplifiees_dossier_number, config
    )

    hedge_data = petition_project.hedge_data
    length_to_remove = hedge_data.length_to_remove()
    length_to_plant = hedge_data.length_to_plant()
    project_details = InstructorInformation(
        slug=None,
        label=None,
        items=[
            Item("Référence", petition_project.reference, None, None),
            "instructor_free_mention",
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_remove()),
                        None,
                        None,
                    ),
                    Item("Total linéaire détruit", length_to_remove, "m", None),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_plant()),
                        None,
                        None,
                    ),
                    Item("Total linéaire planté", length_to_plant, "m", None),
                    Item(
                        "Ratio en longueur",
                        (
                            round(length_to_plant / length_to_remove, 2)
                            if length_to_remove
                            else ""
                        ),
                        None,
                        "Longueur plantée / longueur détruite",
                    ),
                ],
            ),
        ],
    )

    if ds_details:
        if ds_details.city:
            project_details.items.append(
                Item("Commune principale", ds_details.city, None, None)
            )
        if ds_details.applicant_name:
            project_details.items.append(
                Item("Nom du demandeur", ds_details.applicant_name, None, None)
            )

    lineaire_total = moulinette.catalog.get("lineaire_total", "")
    lineaire_detruit_pac = hedge_data.lineaire_detruit_pac()
    motif = moulinette.catalog.get("motif", "")
    bcae8 = InstructorInformation(
        slug="bcae8",
        comment="Seuls les tracés sur parcelle PAC et hors alignement d’arbres sont pris en compte",
        label="BCAE 8",
        items=[
            Item("Total linéaire exploitation déclaré", lineaire_total, "m", None),
            Item(
                "Motif",
                next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
                None,
                None,
            ),
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_remove_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire détruit",
                        hedge_data.lineaire_detruit_pac(),
                        "m",
                        None,
                    ),
                    Item(
                        "Pourcentage détruit / total linéaire",
                        (
                            round(lineaire_detruit_pac / lineaire_total * 100, 2)
                            if lineaire_total
                            else ""
                        ),
                        "%",
                        None,
                    ),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés plantés",
                        len(hedge_data.hedges_to_plant()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire planté",
                        hedge_data.length_to_plant(),
                        "m",
                        None,
                    ),
                    Item(
                        "Ratio en longueur",
                        (
                            round(
                                hedge_data.length_to_plant() / lineaire_detruit_pac, 2
                            )
                            if lineaire_detruit_pac > 0
                            else ""
                        ),
                        None,
                        "Longueur plantée / longueur détruite",
                    ),
                ],
            ),
        ],
    )

    if ds_details:
        if ds_details.pacage:
            bcae8.items.append(Item("N° PACAGE", ds_details.pacage, None, None))

    hedges_to_remove_near_pond = [
        h for h in hedge_data.hedges_to_remove() if h.proximite_mare
    ]
    hedges_to_plant_near_pond = [
        h for h in hedge_data.hedges_to_plant() if h.proximite_mare
    ]

    hedges_to_remove_woodland_connection = [
        h for h in hedge_data.hedges_to_remove() if h.connexion_boisement
    ]
    hedges_to_plant_woodland_connection = [
        h for h in hedge_data.hedges_to_plant() if h.connexion_boisement
    ]

    hedges_to_plant_under_power_line = [
        h for h in hedge_data.hedges_to_plant() if h.sous_ligne_electrique
    ]
    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        items=[
            "onagre_number",
            Item(
                "Présence d'une mare à moins de 200 m",
                ItemDetails(
                    result=len(hedges_to_remove_near_pond) > 0
                    or len(hedges_to_plant_near_pond) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_near_pond))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_remove_near_pond])}"
                                if hedges_to_remove_near_pond
                                else ""
                            ),
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_near_pond))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_near_pond])}"
                                if hedges_to_plant_near_pond
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Connexion à un boisement ou une haie",
                ItemDetails(
                    result=len(hedges_to_remove_woodland_connection) > 0
                    or len(hedges_to_plant_woodland_connection) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_woodland_connection))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_remove_woodland_connection])}"
                                if hedges_to_remove_woodland_connection
                                else ""
                            ),
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_woodland_connection))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_woodland_connection])}"
                                if hedges_to_plant_woodland_connection
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Proximité ligne électrique",
                ItemDetails(
                    result=len(hedges_to_plant_under_power_line) > 0,
                    details=[
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_under_power_line))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_under_power_line])}"
                                if hedges_to_plant_under_power_line
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
        ],
        details=[],
    )

    return ProjectDetails(
        demarches_simplifiees_dossier_number=petition_project.demarches_simplifiees_dossier_number,
        demarche_simplifiee_number=config.demarche_simplifiee_number,
        usager=ds_details.usager if ds_details else "",
        details=[project_details, bcae8, ep],
    )


@dataclass
class DemarchesSimplifieesDetails:
    applicant_name: str | None
    city: str | None
    pacage: str | None
    usager: str


def fetch_project_details_from_demarches_simplifiees(
    dossier_number, config
) -> DemarchesSimplifieesDetails | None:

    if (
        not config.demarches_simplifiees_pacage_id
        or not config.demarches_simplifiees_city_id
    ):
        logger.error(
            "Missing Demarches Simplifiees ids in Haie Config",
            extra={
                "config.id": config.id,
            },
        )
        current_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        admin_url = reverse(
            "admin:moulinette_confighaie_change",
            args=[config.id],
        )
        message = f"""\
        ### Récupération des informations d'un dossier depuis Démarches-simplifiées : :x: erreur

        Les identifiants des champs PACAGE et Commune principale ne sont pas renseignés
        dans la configuration du département {config.department.department}.

        [Admin django](https://{current_site.domain}{admin_url})
        """
        notify(dedent(message), "haie")
        return None

    api_url = settings.DEMARCHES_SIMPLIFIEE["GRAPHQL_API_URL"]
    variables = f"""{{
              "dossierNumber":{dossier_number}
            }}"""
    query = """query getDossier($dossierNumber: Int!) {
          dossier(number: $dossierNumber) {
            id
            number
            state
            usager {
              email
            }
            demandeur {
              ... on PersonnePhysique {
                civilite
                nom
                prenom
                email
              }
            }
            champs {
              id
              stringValue
            }
          }
        }"""

    body = {
        "query": query,
        "variables": variables,
    }
    response = requests.post(
        api_url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEE['GRAPHQL_API_BEARER_TOKEN']}",
        },
    )

    logger.info(
        f"""
            Demarches simplifiees API request status: {response.status_code}"
            * response.text: {response.text},
            * response.status_code: {response.status_code},
            * request.url: {api_url},
            * request.body: {body},
            """,
    )

    if response.status_code >= 400:
        logger.error(
            "Demarches simplifiees API request failed",
            extra={
                "response.text": response.text,
                "response.status_code": response.status_code,
                "request.url": api_url,
                "request.body": body,
            },
        )

        message = f"""\
### Récupération des informations d'un dossier depuis Démarches-simplifiées : :x: erreur

L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier n°{dossier_number}.

Réponse de Démarches Simplifiées : {response.status_code}
```
{response.text}
```

Requête envoyée :
* Url: {api_url}
* Body:
```
{body}
```
"""
        notify(dedent(message), "haie")
        return None

    data = response.json() or {}

    dossier = (data.get("data") or {}).get("dossier")

    if dossier is None:
        logger.error(
            "Demarches simplifiees API response is not well formated",
            extra={
                "response.json": data,
                "response.status_code": response.status_code,
                "request.url": api_url,
                "request.body": body,
            },
        )

        message = f"""\
### Récupération des informations d'un dossier depuis Démarches-simplifiées : :warning: anomalie

La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu. Le dossier concerné n'a pas été récupéré.

Réponse de Démarches Simplifiées : {response.status_code}
```
{response.text}
```

Requête envoyée :
* Url: {api_url}
* Body:
```
{body}
```

"""
        notify(dedent(message), "haie")
        return None
    applicant = dossier.get("demandeur") or {}
    applicant_name = f"{applicant.get('civilite', '')} {applicant.get('prenom', '')} {applicant.get('nom', '')}"
    applicant_name = (
        None
        if applicant_name is None or applicant_name.strip() == ""
        else applicant_name
    )
    city = None
    pacage = None
    champs = dossier.get("champs", [])

    city_field = next(
        (
            champ
            for champ in champs
            if champ["id"] == config.demarches_simplifiees_city_id
        ),
        None,
    )
    if city_field:
        city = city_field.get("stringValue", None)
    pacage_field = next(
        (
            champ
            for champ in champs
            if champ["id"] == config.demarches_simplifiees_pacage_id
        ),
        None,
    )
    if pacage_field:
        pacage = pacage_field.get("stringValue", None)

    usager = (dossier.get("usager") or {}).get("email", "")

    return DemarchesSimplifieesDetails(applicant_name, city, pacage, usager)


def get_moulinette_from_project(petition_project):
    parsed_url = urlparse(petition_project.moulinette_url)
    query_string = parsed_url.query
    # We need to convert the query string to a flat dict
    raw_data = QueryDict(query_string)
    moulinette_data = raw_data.dict()
    moulinette_data["haies"] = petition_project.hedge_data
    moulinette = MoulinetteHaie(
        moulinette_data,
        moulinette_data,
        False,
    )
    return moulinette


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

        if self.object:
            lines.append("#### Mapping avec Démarches-simplifiées : :warning: anomalie")
            projet_relative_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.object.id],
            )
            projet_url = self.request.build_absolute_uri(projet_relative_url)

            lines.append("Un dossier a été créé sur démarches-simplifiées : ")
            lines.append(f"* [projet dans l’admin]({projet_url})")

            if self.config:
                dossier_url = (
                    f"https://www.demarches-simplifiees.fr/procedures/"
                    f"{self.config.demarche_simplifiee_number}/dossiers/"
                    f"{self.object.demarches_simplifiees_dossier_number}"
                )
                lines.append(
                    f"* [dossier DS n°{self.object.demarches_simplifiees_dossier_number}]"
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
