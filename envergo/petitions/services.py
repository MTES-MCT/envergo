import json
import logging
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, List, Literal

import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.petitions.tests.factories import DEMARCHES_SIMPLIFIEES_FAKE_DOSSIER
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
    """Instructor information details class formatted to be displayed in templates"""

    label: str
    items: list[Item]


@dataclass
class InstructorInformation:
    """Instructor information class formatted to be displayed in templates"""

    slug: str | None
    label: str | None
    items: list[Item | Literal["instructor_free_mention", "onagre_number"]]
    details: list[InstructorInformationDetails]
    comment: str | None = None


@dataclass
class ProjectDetails:
    """Project details class formatted to be displayed in templates"""

    demarches_simplifiees_dossier_number: int
    demarche_simplifiee_number: int
    usager: str
    details: list[InstructorInformation]
    ds_data: dict


def compute_instructor_informations(
    petition_project, moulinette, site, visitor_id, user
) -> ProjectDetails:
    """Build ProjectDetails with instructor informations"""

    config = moulinette.config
    ds_details = compute_instructor_ds_informations(
        petition_project, config, site, visitor_id, user
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
                    Item("Total linéaire détruit", round(length_to_remove), "m", None),
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
                    Item("Total linéaire planté", round(length_to_plant), "m", None),
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
                        round(hedge_data.lineaire_detruit_pac()),
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
                        len(hedge_data.hedges_to_plant_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire planté",
                        round(hedge_data.length_to_plant_pac()),
                        "m",
                        None,
                    ),
                    Item(
                        "Ratio en longueur",
                        (
                            round(
                                hedge_data.length_to_plant_pac() / lineaire_detruit_pac,
                                2,
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
        ds_data=ds_details,
    )


@dataclass
class DemarchesSimplifieesDetails:
    applicant_name: str | None
    city: str | None
    pacage: str | None
    usager: str
    champs: dict


def compute_instructor_ds_informations(
    petition_project, config, site, visitor_id, user
) -> DemarchesSimplifieesDetails:
    dossier = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, visitor_id, user
    )
    if not dossier:
        return None

    dossier_number = petition_project.demarches_simplifiees_dossier_number

    demarche_name = dossier.get("demarche", {}).get("title", "Nom inconnu")
    demarche_number = dossier.get("demarche", {}).get("number", "Numéro inconnu")
    demarche_label = f"la démarche n°{demarche_number} ({demarche_name})"

    ds_url = (
        f"https://www.demarches-simplifiees.fr/procedures/{demarche_number}/dossiers/"
        f"{dossier_number}"
    )
    petition_project.synchronize_with_demarches_simplifiees(
        dossier, site, demarche_label, ds_url, visitor_id, user
    )
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

    return DemarchesSimplifieesDetails(applicant_name, city, pacage, usager, champs)


def fetch_project_details_from_demarches_simplifiees(
    petition_project, config, site, visitor_id, user
) -> dict() | None:
    dossier_number = petition_project.demarches_simplifiees_dossier_number

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
        admin_url = reverse(
            "admin:moulinette_confighaie_change",
            args=[config.id],
        )
        message = render_to_string(
            "haie/petitions/mattermost_demarches_simplifiees_donnees_manquantes.txt",
            context={
                "department": config.department.department,
                "domain": site.domain,
                "admin_url": admin_url,
            },
        )
        notify(dedent(message), "haie")
        return None

    api_url = settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"]
    variables = f"""{{
              "dossierNumber":{dossier_number}
            }}"""
    query = """query getDossier($dossierNumber: Int!) {
          dossier(number: $dossierNumber) {
            id
            number
            state
            dateDepot
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
            demarche{
                title
                number
            }
          }
        }"""

    body = {
        "query": query,
        "variables": variables,
    }

    dossier = None

    if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
        logger.warning(
            f"Demarches Simplifiees is not enabled. Doing nothing. Use fake dossier."
            f"\nrequest.url: {api_url}"
            f"\nrequest.body: {body}"
        )
        dossier = json.loads(DEMARCHES_SIMPLIFIEES_FAKE_DOSSIER)

    else:
        response = requests.post(
            api_url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEES['GRAPHQL_API_BEARER_TOKEN']}",
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

            message = render_to_string(
                "haie/petitions/mattermost_demarches_simplifiees_api_error_one_dossier.txt",
                context={
                    "dossier_number": dossier_number,
                    "status_code": response.status_code,
                    "response": response.text,
                    "api_url": api_url,
                    "body": body,
                },
            )
            notify(dedent(message), "haie")
            return None

        data = response.json() or {}

        dossier = (data.get("data") or {}).get("dossier")

    if dossier is None:

        if (
            any(
                error["extensions"]["code"] == "not_found"
                for error in data.get("errors") or []
            )
            and not petition_project.is_dossier_submitted
        ):
            # the dossier is not found, but it's normal if the project is not submitted
            logger.info(
                "A Demarches simplifiees dossier is not found, but the project is not marked as submitted yet",
                extra={
                    "response.json": data,
                    "response.status_code": response.status_code,
                    "request.url": api_url,
                    "request.body": body,
                },
            )
            return None

        logger.error(
            "Demarches simplifiees API response is not well formated",
            extra={
                "response.json": data,
                "response.status_code": response.status_code,
                "request.url": api_url,
                "request.body": body,
            },
        )

        message = render_to_string(
            "haie/petitions/mattermost_demarches_simplifiees_api_unexpected_format.txt",
            context={
                "status_code": response.status_code,
                "response": response.text,
                "api_url": api_url,
                "body": body,
                "command": "fetch_project_details_from_demarches_simplifiees",
            },
        )
        notify(dedent(message), "haie")
        return None
    # we have got a dossier from DS for this petition project

    return dossier


class PetitionProjectCreationProblem:
    """An object to store a problem during the creation of a petition project"""

    def __init__(self, key, extra: dict[str, Any] = dict, is_fatal=False):
        self.key = key
        self.extra = extra
        self.is_fatal = is_fatal

    def compute_message(self, index):
        return render_to_string(
            "haie/petitions/mattermost_project_creation_problem.txt",
            context={
                "index": index,
                "problem": self,
            },
        )


class PetitionProjectCreationAlert(List[PetitionProjectCreationProblem]):
    """This class list all the problems that occured during the creation of a petition project.
    It can then be used to generate a notification to send to the admin."""

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

    def append(self, item: PetitionProjectCreationProblem) -> None:
        if not isinstance(item, PetitionProjectCreationProblem):
            raise TypeError("Only Alert instances can be added to AlertList")
        super().append(item)

    def compute_message(self):
        config_url = None
        if self.config:
            config_relative_url = reverse(
                "admin:moulinette_confighaie_change", args=[self.config.id]
            )
            config_url = self.request.build_absolute_uri(config_relative_url)

        if self._petition_project:
            projet_relative_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self._petition_project.id],
            )
            projet_url = self.request.build_absolute_uri(projet_relative_url)
            dossier_url = None
            if self.config:
                dossier_url = (
                    f"https://www.demarches-simplifiees.fr/procedures/"
                    f"{self.config.demarche_simplifiee_number}/dossiers/"
                    f"{self._petition_project.demarches_simplifiees_dossier_number}"
                )

            message = render_to_string(
                "haie/petitions/mattermost_project_creation_anomalie.txt",
                context={
                    "projet_url": projet_url,
                    "config": self.config,
                    "config_url": config_url,
                    "dossier_url": dossier_url,
                    "demarches_simplifiees_dossier_number": self._petition_project.demarches_simplifiees_dossier_number,
                },
            )
        else:
            message = render_to_string(
                "haie/petitions/mattermost_project_creation_erreur.txt",
                context={
                    "config_url": config_url,
                    "department": self.config.department,
                    "user_error_reference": self.user_error_reference.upper(),
                    "form": display_form_details(self.form),
                },
            )

        index = 0
        for alert in self:
            index = index + 1
            message = message + "\n" + alert.compute_message(index)

        return message
