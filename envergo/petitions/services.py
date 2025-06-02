import json
import logging
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, List, Literal

import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.module_loading import import_string

from envergo.hedges.forms import MODE_DESTRUCTION_CHOICES, MODE_PLANTATION_CHOICES
from envergo.hedges.models import Hedge
from envergo.utils.mattermost import notify
from envergo.utils.tools import display_form_details

logger = logging.getLogger(__name__)


@dataclass
class AdditionalInfo:
    label: str
    value: str | int | float
    unit: str | None


@dataclass
class FileInfo:
    filename: str
    content_type: str
    url: str


@dataclass
class ItemFiles:
    files: list[FileInfo]


@dataclass
class ItemDetails:
    result: bool
    details: list[AdditionalInfo]
    display_result: bool = True


@dataclass
class Item:
    label: str
    value: str | int | float | ItemDetails
    unit: str | None
    comment: str | None

    @classmethod
    def from_field(cls, field, field_value):
        """Fill the item from a field"""
        label = field.display_label if hasattr(field, "display_label") else field.label
        unit = field.display_unit if hasattr(field, "display_unit") else None
        if hasattr(field, "get_display_value"):
            value = field.get_display_value(field_value)
        elif hasattr(field, "choices"):
            value = dict(field.choices).get(field_value, field_value)
        else:
            value = field_value

        comment = (
            field.display_help_text if hasattr(field, "display_help_text") else None
        )
        return cls(label, value, unit, comment)


@dataclass
class Title:
    label: str


ItemType = (
    Item
    | Title
    | Literal[
        "instructor_free_mention",
        "onagre_number",
        "protected_species",
        "moulinette_fields",
        "display_hedges_cta",
        "open_simulation_cta",
        "hedges_compensation_details",
    ]
)


@dataclass
class GroupedItems:
    """Instructor information details class formatted to be displayed in templates"""

    label: str
    items: list[ItemType | "GroupedItems"]


@dataclass
class InstructorInformation:
    """Instructor information class formatted to be displayed in templates"""

    slug: str | None
    label: str | None
    key_elements: list[ItemType | "GroupedItems"] | None
    simulation_data: list[ItemType | "GroupedItems"] | None
    other_items: list[ItemType | "GroupedItems"] | None = None
    comment: str | None = None


@dataclass
class DemarchesSimplifieesDetails:
    applicant_name: str | None
    city: str | None
    pacage: str | None
    usager: str
    header_sections: list | None
    champs: list | None


@dataclass
class ProjectDetails:
    """Project details class formatted to be displayed in templates"""

    demarches_simplifiees_dossier_number: int
    demarche_simplifiee_number: int
    usager: str
    sections: list[InstructorInformation]
    ds_data: DemarchesSimplifieesDetails | None


class HedgeList(list[Hedge]):
    def __init__(self, *args, label=None, **kwargs):
        self.label = label
        super().__init__(*args, **kwargs)

    @property
    def length(self):
        return sum(h.length for h in self)

    @property
    def names(self):
        return ", ".join(h.id for h in self)


def get_project_context(petition_project, moulinette) -> dict:
    """Build context for petition project instructor page view"""

    hedge_data = petition_project.hedge_data
    length_to_remove = hedge_data.length_to_remove()
    length_to_plant = hedge_data.length_to_plant()

    hedge_to_remove_by_destruction_mode = {
        mode: HedgeList(label=label) for mode, label in MODE_DESTRUCTION_CHOICES
    }

    for hedge in hedge_data.hedges_to_remove():
        hedge_to_remove_by_destruction_mode[hedge.mode_destruction].append(hedge)

    hedge_to_plant_properties_form = import_string(
        moulinette.config.hedge_to_plant_properties_form
    )
    plantation_details = {}
    if "mode_plantation" in hedge_to_plant_properties_form.base_fields:
        hedge_to_plant_by_plantation_mode = {
            key: HedgeList(label=label) for key, _, label in MODE_PLANTATION_CHOICES
        }

        for hedge in hedge_data.hedges_to_plant():
            if hedge.mode_plantation is not None:
                hedge_to_plant_by_plantation_mode[hedge.mode_plantation].append(hedge)

        plantation_details = {
            "plantation_only_ratio": (
                hedge_to_plant_by_plantation_mode["plantation"].length
                / length_to_remove
                if length_to_remove
                else ""
            ),
            "hedge_to_plant_by_plantation_mode": hedge_to_plant_by_plantation_mode,
        }

    context = {
        "length_to_remove": length_to_remove,
        "hedge_to_remove_by_destruction_mode": hedge_to_remove_by_destruction_mode,
        "length_to_plant": length_to_plant,
        "plantation_ratio": (
            length_to_plant / length_to_remove if length_to_remove else ""
        ),
    }
    context.update(plantation_details)

    return context


def get_instructor_view_context(
    petition_project, moulinette, site, visitor_id, user
) -> dict:
    """Build context for ProjectDetails instructor page view"""

    # Build project details
    project_summary = get_project_context(petition_project, moulinette)

    # Get ds details
    config = moulinette.config
    dossier = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, visitor_id, user
    )

    city = None
    pacage = None
    ds_details = None

    if dossier:
        applicant = dossier.get("demandeur") or {}
        applicant_name = f"{applicant.get('civilite', '')} {applicant.get('prenom', '')} {applicant.get('nom', '')}"
        applicant_name = (
            None
            if applicant_name is None or applicant_name.strip() == ""
            else applicant_name
        )
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

        ds_details = DemarchesSimplifieesDetails(
            applicant_name, city, pacage, usager, None, None
        )

    context = {
        "demarches_simplifiees_dossier_number": petition_project.demarches_simplifiees_dossier_number,
        "demarche_simplifiee_number": config.demarche_simplifiee_number,
        "usager": ds_details.usager if ds_details else "",
        "ds_data": ds_details,
    }
    context.update(project_summary)

    return context


def compute_instructor_informations_ds(
    petition_project, moulinette, site, visitor_id, user
) -> ProjectDetails:
    """Compute ProjectDetails with instructor informations"""

    # Build project details
    project_summary = get_project_context(petition_project, moulinette)

    # Get ds details
    config = moulinette.config

    dossier = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, visitor_id, user
    )

    if not dossier:
        return ProjectDetails(
            demarches_simplifiees_dossier_number=petition_project.demarches_simplifiees_dossier_number,
            demarche_simplifiee_number=config.demarche_simplifiee_number,
            usager="",
            sections=[project_summary],
            ds_data=None,
        )

    applicant = dossier.get("demandeur") or {}
    applicant_name = f"{applicant.get('civilite', '')} {applicant.get('prenom', '')} {applicant.get('nom', '')}"
    applicant_name = (
        None
        if applicant_name is None or applicant_name.strip() == ""
        else applicant_name
    )
    demarche = dossier.get("demarche")
    header_sections = None
    champs = dossier.get("champs", [])

    if demarche:
        header_sections, explication_champs_ids = (
            get_header_explanation_from_ds_demarche(demarche)
        )

    usager = (dossier.get("usager") or {}).get("email", "")

    # Build champs_display list without explication_champs
    champs_display = [
        Item(
            c.get("label"),
            get_item_value_from_ds_champs(c),
            None,
            None,
        )
        for c in champs
        if c.get("id") not in explication_champs_ids
    ]

    ds_details = DemarchesSimplifieesDetails(
        applicant_name, None, None, usager, header_sections, champs_display
    )

    return ProjectDetails(
        demarches_simplifiees_dossier_number=petition_project.demarches_simplifiees_dossier_number,
        demarche_simplifiee_number=config.demarche_simplifiee_number,
        usager=ds_details.usager if ds_details else "",
        sections=[project_summary],
        ds_data=ds_details,
    )


def get_item_value_from_ds_champs(champs):
    """get item value from dossier champs
    Ok better to do with yesno filter…
    """

    type_name = champs.get("__typename") or ""
    value = champs.get("stringValue") or ""

    if type_name == "CheckboxChamp":
        if champs.get("checked"):
            value = "oui"
        else:
            value = "non"
    elif type_name == "YesNoChamp":
        if champs.get("selected"):
            value = "oui"
        else:
            value = "non"
    elif type_name == "PieceJustificativeChamp":
        pieces = champs.get("files") or []
        value = ItemFiles(
            [
                FileInfo(
                    p["filename"],
                    p["contentType"],
                    p["url"],
                )
                for p in pieces
            ]
        )

    return value


def get_header_explanation_from_ds_demarche(demarche):
    """Get header sections and explanation from demarche champDescriptors"""

    champ_descriptors = demarche.get("revision", {}).get("champDescriptors", [])
    header_sections = []
    explication_champs = []

    if champ_descriptors:
        for champ_descriptor in champ_descriptors:
            type_name = champ_descriptor.get("__typename", "")
            if type_name == "HeaderSectionChampDescriptor":
                label = champ_descriptor.get("label", "")
                header_sections.append(label)
            if type_name == "ExplicationChampDescriptor":
                champ_id = champ_descriptor.get("id")
                explication_champs.append(champ_id)

    return header_sections, explication_champs


def fetch_project_details_from_demarches_simplifiees(
    petition_project, config, site, visitor_id, user
) -> dict | None:
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

    query = ""

    with open(
        Path(
            settings.APPS_DIR
            / "petitions"
            / "demarches_simplifiees"
            / "queries"
            / "get_dossier.gql"
        ),
        "r",
    ) as file:
        query = file.read()

    body = {
        "query": query,
        "variables": variables,
    }

    dossier = None

    if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
        logger.warning(
            f"Demarches Simplifiees is not enabled. Doing nothing."
            f"Use fake dossier if dossier is not draft."
            f"\nrequest.url: {api_url}"
            f"\nrequest.body: {body}"
        )
        with open(
            Path(
                settings.APPS_DIR
                / "petitions"
                / "demarches_simplifiees"
                / "data"
                / "fake_dossier.json"
            ),
            "r",
        ) as file:
            response = json.load(file)
            dossier = response.get("data", {}).get("dossier") or {}
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

    # we have got a dossier from DS for this petition project,
    # let's synchronize project
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
