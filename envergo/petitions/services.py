import datetime
import logging
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, List

from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.module_loading import import_string

from envergo.hedges.forms import MODE_DESTRUCTION_CHOICES, MODE_PLANTATION_CHOICES
from envergo.hedges.models import HedgeList
from envergo.petitions.demarches_simplifiees.client import (
    DemarchesSimplifieesClient,
    DemarchesSimplifieesError,
)
from envergo.petitions.demarches_simplifiees.models import (
    CheckboxChamp,
    Dossier,
    DossierState,
    ExplicationChampDescriptor,
    HeaderSectionChampDescriptor,
    PieceJustificativeChamp,
    YesNoChamp,
)
from envergo.utils.mattermost import notify
from envergo.utils.tools import display_form_details

logger = logging.getLogger(__name__)


DEMARCHES_SIMPLIFIEES_STATUS_MAPPING = {
    ("to_be_processed", "unset"): "en_construction",
    ("to_be_processed", "express_agreement"): "en_construction",
    ("to_be_processed", "tacit_agreement"): "en_construction",
    ("to_be_processed", "opposition"): "en_construction",
    ("to_be_processed", "dropped"): "en_construction",
    ("instruction_d", "unset"): "en_instruction",
    ("instruction_d", "express_agreement"): "en_instruction",
    ("instruction_d", "tacit_agreement"): "en_instruction",
    ("instruction_d", "opposition"): "en_instruction",
    ("instruction_d", "dropped"): "en_instruction",
    ("instruction_a", "unset"): "en_instruction",
    ("instruction_a", "express_agreement"): "en_instruction",
    ("instruction_a", "tacit_agreement"): "en_instruction",
    ("instruction_a", "opposition"): "en_instruction",
    ("instruction_a", "dropped"): "en_instruction",
    ("instruction_h", "unset"): "en_instruction",
    ("instruction_h", "express_agreement"): "en_instruction",
    ("instruction_h", "tacit_agreement"): "en_instruction",
    ("instruction_h", "opposition"): "en_instruction",
    ("instruction_h", "dropped"): "en_instruction",
    ("preparing_decision", "unset"): "en_instruction",
    ("preparing_decision", "express_agreement"): "en_instruction",
    ("preparing_decision", "tacit_agreement"): "en_instruction",
    ("preparing_decision", "opposition"): "en_instruction",
    ("preparing_decision", "dropped"): "en_instruction",
    ("notification", "unset"): "en_instruction",
    ("notification", "express_agreement"): "en_instruction",
    ("notification", "tacit_agreement"): "en_instruction",
    ("notification", "opposition"): "en_instruction",
    ("notification", "dropped"): "en_instruction",
    ("closed", "express_agreement"): "accepte",
    ("closed", "tacit_agreement"): "accepte",
    ("closed", "opposition"): "refuse",
    ("closed", "dropped"): "sans_suite",
}


@dataclass
class FileInfo:
    filename: str
    content_type: str
    url: str


@dataclass
class ItemFiles:
    files: list[FileInfo]


@dataclass
class Item:
    label: str
    value: str | int | float
    unit: str | None
    comment: str | None


@dataclass
class DemarchesSimplifieesDetails:
    header_sections: list | None
    champs: list | None


def get_project_context(petition_project, moulinette) -> dict:
    """Get parts of context for instructor pages from the PetitionProject"""

    hedge_data = petition_project.hedge_data
    length_to_remove = hedge_data.length_to_remove()
    length_to_plant = hedge_data.length_to_plant()

    hedge_to_remove_by_destruction_mode = {
        mode: HedgeList(label=label) for mode, _, label in MODE_DESTRUCTION_CHOICES
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


def get_context_from_ds(petition_project, moulinette) -> dict:
    """Get parts of context for instructor pages from Demarches Simplifiées"""
    # Get ds details
    config = moulinette.config
    dossier = get_demarches_simplifiees_dossier(petition_project)

    city = ""
    pacage = ""
    organization = ""
    usager = ""
    applicant = ""

    if (
        not config.demarches_simplifiees_pacage_id
        or not config.demarches_simplifiees_city_id
        or not config.demarches_simplifiees_organization_id
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
        current_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        message = render_to_string(
            "haie/petitions/mattermost_demarches_simplifiees_donnees_manquantes.txt",
            context={
                "department": config.department.department,
                "domain": current_site.domain,
                "admin_url": admin_url,
            },
        )
        notify(dedent(message), "haie")

    if dossier:
        city, organization, pacage = extract_data_from_fields(config, dossier)
        usager = dossier.usager.email or ""
        applicant = dossier.applicant_name or ""

    context = {
        "demarches_simplifiees_dossier_number": petition_project.demarches_simplifiees_dossier_number,
        "demarche_simplifiee_number": config.demarche_simplifiee_number,
        "usager": usager,
        "city": city,
        "pacage": pacage,
        "organization": organization,
        "applicant": applicant,
    }

    return context


def get_field_data_from_ds_dossier(field_id, dossier):
    """Get field value from dossier DS with id"""
    champs = dossier.champs
    field = next(
        (champ for champ in champs if champ.id == field_id),
        None,
    )
    if not field:
        return None
    item = Item(
        field.label,
        get_item_value_from_ds_champ(field),
        None,
        None,
    )
    return item


def extract_data_from_fields(config, dossier):
    """Extract the data of the known fields in config from the Demarches Simplifiees dossier."""
    city = ""
    pacage = ""
    organization = ""

    champs = dossier.champs
    city_field = next(
        (champ for champ in champs if champ.id == config.demarches_simplifiees_city_id),
        None,
    )
    if city_field:
        city = city_field.stringValue
    pacage_field = next(
        (
            champ
            for champ in champs
            if champ.id == config.demarches_simplifiees_pacage_id
        ),
        None,
    )
    if pacage_field:
        pacage = pacage_field.stringValue
    organization_field = next(
        (
            champ
            for champ in champs
            if champ.id == config.demarches_simplifiees_organization_id
        ),
        None,
    )
    if organization_field:
        organization = organization_field.stringValue

    return city, organization, pacage


def compute_instructor_informations_ds(
    petition_project,
) -> DemarchesSimplifieesDetails | None:
    """Compute ProjectDetails with instructor informations"""
    # Get ds details
    dossier = get_demarches_simplifiees_dossier(petition_project, force_update=True)

    if not dossier:
        return None

    demarche = dossier.demarche
    champs = dossier.champs

    header_sections, explication_champs_ids = get_header_explanation_from_ds_demarche(
        demarche
    )

    # Build champs_display list without explication_champs
    champs_display = [
        Item(
            c.label,
            get_item_value_from_ds_champ(c),
            None,
            None,
        )
        for c in champs
        if c.id not in explication_champs_ids
    ]

    ds_details = DemarchesSimplifieesDetails(
        header_sections,
        champs_display,
    )

    return ds_details


def get_messages_and_senders_from_ds(
    petition_project,
) -> (List | None, List | None, str | None):
    """Get messages and sender emails from DS

    :param petition_project: PetitionProject object

    :return: tuple (messages list, instructor emails list, petitioner email)
    """

    # Get messages only from DS
    dossier_number = petition_project.demarches_simplifiees_dossier_number
    ds_client = DemarchesSimplifieesClient()
    dossier_with_messages_as_dict = ds_client.get_dossier_messages(dossier_number)

    if not dossier_with_messages_as_dict:
        logger.error(
            f"Cannot get messages from Démarches Simplifiées for dossier number {dossier_number}"
        )
        return None, None, None

    dossier = Dossier.from_dict(dossier_with_messages_as_dict)
    petitioner_email = dossier.usager.email
    instructor_emails = dossier.instructor_emails

    messages = sorted(
        dossier.messages, key=lambda message: message.createdAt, reverse=True
    )
    return messages, instructor_emails, petitioner_email


def send_message_dossier_ds(petition_project, message_body, attachment_file=None):
    """Send message via DS API for a given dossier"""

    # Get dossier ID
    dossier_number = petition_project.demarches_simplifiees_dossier_number
    dossier_id = petition_project.demarches_simplifiees_dossier_id
    if not dossier_id or not dossier_number:
        return None

    # Send message
    ds_client = DemarchesSimplifieesClient()
    if attachment_file:
        response = ds_client.dossier_send_message(
            dossier_number, dossier_id, message_body, attachment_file
        )
    else:
        response = ds_client.dossier_send_message(
            dossier_number, dossier_id, message_body
        )

    return response


def get_item_value_from_ds_champ(champ):
    """get item value from a dossier champ
    Ok better to do with yesno filter…
    """

    value = champ.stringValue or ""

    if isinstance(champ, CheckboxChamp):
        if champ.stringValue == "true":
            value = "oui"
        else:
            value = "non"
    elif isinstance(champ, YesNoChamp):
        if champ.stringValue == "true":
            value = "oui"
        else:
            value = "non"
    elif isinstance(champ, PieceJustificativeChamp):
        pieces = champ.files or []
        value = ItemFiles(
            [
                FileInfo(
                    p.filename,
                    p.contentType,
                    p.url,
                )
                for p in pieces
            ]
        )

    return value


def get_header_explanation_from_ds_demarche(demarche):
    """Get header sections and explanation from demarche champDescriptors"""

    champ_descriptors = demarche.revision.champDescriptors
    header_sections = []
    explication_champs = []

    if champ_descriptors:
        for champ_descriptor in champ_descriptors:
            if isinstance(champ_descriptor, HeaderSectionChampDescriptor):
                label = champ_descriptor.label
                header_sections.append(label)
            if isinstance(champ_descriptor, ExplicationChampDescriptor):
                champ_id = champ_descriptor.id
                explication_champs.append(champ_id)

    return header_sections, explication_champs


def get_demarches_simplifiees_dossier(
    petition_project,
    force_update: bool = False,
) -> Dossier | None:
    """Get dossier from Demarches Simplifiees either from DB if it is up to date, or from Demarches Simplifiees API.

    args:
        petition_project: The petition project to update with the fetched details.
        force_update: If True, forces an update from Demarches Simplifiees even if the last sync is recent.
    returns:
        Dossier object if found, None otherwise.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    one_hour_ago_utc = now_utc - datetime.timedelta(hours=1)
    if (
        force_update
        or not petition_project.demarches_simplifiees_raw_dossier
        or petition_project.demarches_simplifiees_last_sync is not None
        and petition_project.demarches_simplifiees_last_sync < one_hour_ago_utc
    ):
        # If the last sync is older than one hour, we fetch the dossier from Demarches Simplifiees
        dossier_number = petition_project.demarches_simplifiees_dossier_number

        ds_client = DemarchesSimplifieesClient()

        dossier_as_dict = ds_client.get_dossier(dossier_number)

        if dossier_as_dict is not None:
            # we have got a dossier from DS for this petition project,
            # let's synchronize project
            petition_project.synchronize_with_demarches_simplifiees(dossier_as_dict)
    else:
        # If the last sync is recent, we can use the cached dossier from the petition project
        dossier_as_dict = petition_project.demarches_simplifiees_raw_dossier

    dossier = Dossier.from_dict(dossier_as_dict) if dossier_as_dict else None
    return dossier


def update_demarches_simplifiees_status(petition_project, new_status):
    client = DemarchesSimplifieesClient()

    if petition_project.demarches_simplifiees_dossier_id is None:
        # ensure that we have the dossier first because we need its id
        get_demarches_simplifiees_dossier(petition_project, force_update=True)

        if petition_project.demarches_simplifiees_dossier_id is None:
            # this dossier cannot be fetched on DS, maybe it is in draft. We cannot update its status.
            raise ValueError("Cannot update status of a dossier without DS id")

    if new_status == DossierState.en_construction.value:
        response = client.pass_back_dossier_under_construction(
            petition_project.reference,
            petition_project.demarches_simplifiees_dossier_id,
        )
    elif new_status == DossierState.en_instruction.value:
        if petition_project.demarches_simplifiees_state in [
            DossierState.accepte.value,
            DossierState.refuse.value,
            DossierState.sans_suite.value,
        ]:
            response = client.pass_back_dossier_to_instruction(
                petition_project.reference,
                petition_project.demarches_simplifiees_dossier_id,
            )
        else:
            response = client.pass_dossier_to_instruction(
                petition_project.reference,
                petition_project.demarches_simplifiees_dossier_id,
            )
    elif new_status == DossierState.accepte.value:
        response = client.accept_dossier(
            petition_project.reference,
            petition_project.demarches_simplifiees_dossier_id,
        )
    elif new_status == DossierState.refuse.value:
        response = client.refuse_dossier(
            petition_project.reference,
            petition_project.demarches_simplifiees_dossier_id,
            "La demande a été refusée. Consulter la messagerie pour plus de précisions.",
        )
    elif new_status == DossierState.sans_suite.value:
        response = client.close_dossier(
            petition_project.reference,
            petition_project.demarches_simplifiees_dossier_id,
            "La demande a été classée sans suite. Consulter la messagerie pour plus de précisions.",
        )
    else:
        raise ValueError(f"Unknown status {new_status}")

    if response:
        # the status change was successful, we update the petition project
        petition_project.demarches_simplifiees_state = response["dossier"]["state"]
        petition_project.synchronize_with_demarches_simplifiees(response["dossier"])
    else:
        # update failed, notification should have been sent by the DS client
        raise DemarchesSimplifieesError(
            "", {}, "Unable to update status on Démarches Simplifiées"
        )


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
            dossier_url = self._petition_project.demarches_simplifiees_petitioner_url
            if self.config:
                dossier_url = (
                    self._petition_project.get_demarches_simplifiees_instructor_url(
                        self.config.demarche_simplifiee_number
                    )
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
