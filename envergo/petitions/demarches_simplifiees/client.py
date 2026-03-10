import copy
import hashlib
import json
import logging
from base64 import b64encode
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from textwrap import dedent

import requests
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.template.loader import render_to_string
from gql import Client, gql
from gql.transport.exceptions import TransportError
from gql.transport.requests import RequestsHTTPTransport
from graphql import GraphQLError

from envergo.petitions.demarches_simplifiees.models import (
    DemarcheWithRawDossiers,
    DossierState,
)
from envergo.petitions.demarches_simplifiees.queries import (
    DOSSIER_ACCEPTER_MUTATION,
    DOSSIER_CLASSER_SANS_SUITE_MUTATION,
    DOSSIER_CREATE_DIRECT_UPLOAD_MUTATION,
    DOSSIER_ENVOYER_MESSAGE_MUTATION,
    DOSSIER_PASSER_EN_INSTRUCTION_MUTATION,
    DOSSIER_REFUSER_MUTATION,
    DOSSIER_REPASSER_EN_CONSTRUCTION_MUTATION,
    DOSSIER_REPASSER_EN_INSTRUCTION_MUTATION,
    GET_DOSSIER_MESSAGES_QUERY,
    GET_DOSSIER_QUERY,
    GET_DOSSIERS_FOR_DEMARCHE_QUERY,
)
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH = Path(
    settings.APPS_DIR / "petitions" / "demarches_simplifiees" / "data"
)

DS_DISABLED_BASE_MESSAGE = "Demarches Simplifiees is not enabled. Doing nothing. Use fake dossier if dossier is not draft."  # noqa: E501


class DemarchesSimplifieesClient:
    def __init__(self):
        self.transport = RequestsHTTPTransport(
            url=settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"],
            headers={
                "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEES['GRAPHQL_API_BEARER_TOKEN']}"
            },
        )
        self.client = Client(
            transport=self.transport, fetch_schema_from_transport=False
        )

    def _fake_execute(self, fake_dossier_filename):
        """Mock response when Demarches Simplifiees is not enabled"""
        with open(
            DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH / fake_dossier_filename,
            "r",
        ) as file:
            response = json.load(file)
            return copy.deepcopy(response["data"])

    def execute(self, query_str: str, variables: dict = None):
        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            raise NotImplementedError("Démarches simplifiées is not enabled")

        query = gql(query_str)
        try:
            result = self.client.execute(query, variable_values=variables or {})
            logger.info(
                "Demarches simplifiees API request succeed",
                extra={
                    "result": result,
                    "query": query_str,
                    "variables": variables,
                },
            )

        except (TransportError, GraphQLError, ConnectionError) as e:
            logger.error(
                "Demarches simplifiees API request failed",
                extra={
                    "error": e,
                    "query": query_str,
                    "variables": variables,
                },
            )
            raise DemarchesSimplifieesError(
                query=query_str,
                variables=variables,
                message=str(e),
            ) from e

        return result

    def _fetch_dossier(
        self,
        dossier_number,
        query,
        fake_dossier_filename,
    ) -> dict | None:
        """Fetch dossier from DS, using specific query and fake dossier filename"""

        variables = {"dossierNumber": dossier_number}

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"{DS_DISABLED_BASE_MESSAGE}"
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            data = self._fake_execute(fake_dossier_filename)

        else:
            try:
                data = self.execute(query, variables)
            except DemarchesSimplifieesError as e:
                if any(
                    error.get("extensions", {}).get("code") == "not_found"
                    and any(path == "dossier" for path in error.get("path", []))
                    for error in (
                        e.__cause__.errors if hasattr(e.__cause__, "errors") else []
                    )
                ):
                    logger.info(
                        "A Demarches simplifiees dossier is not found, but the project is not marked as submitted yet",
                        extra={
                            "dossier_number": dossier_number,
                            "error": e.__cause__ if e.__cause__ else e.message,
                            "query": e.query,
                            "variables": e.variables,
                        },
                    )
                else:
                    message = render_to_string(
                        "haie/petitions/mattermost_demarches_simplifiees_api_error_one_dossier.txt",
                        context={
                            "dossier_number": dossier_number,
                            "error": e.__cause__ if e.__cause__ else e.message,
                            "query": e.query,
                            "variables": e.variables,
                        },
                    )
                    notify(dedent(message), "haie")
                return None

        if "dossier" not in data or not data["dossier"]:
            logger.error(
                "Demarches simplifiees API response is not well formated",
                extra={
                    "response": data,
                    "query": query,
                    "variables": variables,
                },
            )

            message = render_to_string(
                "haie/petitions/mattermost_demarches_simplifiees_api_unexpected_format.txt",
                context={
                    "response": data,
                    "query": query,
                    "variables": variables,
                },
            )
            notify(dedent(message), "haie")
            return None

        return data["dossier"]

    def get_dossier(self, dossier_number):
        """Get dossier"""
        fake_dossier_filename = "fake_dossier.json"

        data = self._fetch_dossier(
            dossier_number, GET_DOSSIER_QUERY, fake_dossier_filename
        )

        return data

    def get_dossier_messages(self, dossier_number):
        """Get dossier messages only"""
        fake_dossier_filename = "fake_dossier_messages.json"

        data = self._fetch_dossier(
            dossier_number, GET_DOSSIER_MESSAGES_QUERY, fake_dossier_filename
        )

        return data

    def get_dossiers_for_demarche(
        self, demarche_number, dossiers_updated_since: datetime
    ) -> DemarcheWithRawDossiers | None:
        first_page = self._fetch_dossiers_page(demarche_number, dossiers_updated_since)
        demarche = DemarcheWithRawDossiers.from_dict(first_page["demarche"])
        demarche.set_dossier_iterator(
            lambda cursor: self._fetch_dossiers_page(
                demarche_number, dossiers_updated_since, cursor
            ),
            first_page["dossiers"],
            first_page["hasNextPage"],
            first_page["endCursor"],
        )
        return demarche

    def _fetch_dossiers_page(
        self, demarche_number: str, dossiers_updated_since: datetime, cursor: str = None
    ) -> dict:

        variables = {
            "demarcheNumber": demarche_number,
            "updatedSince": dossiers_updated_since.isoformat(),
            "after": cursor,
        }
        try:
            data = self.execute(GET_DOSSIERS_FOR_DEMARCHE_QUERY, variables)
        except DemarchesSimplifieesError as e:
            message_body = render_to_string(
                "haie/petitions/mattermost_demarches_simplifiees_api_error.txt",
                context={
                    "demarche_number": demarche_number,
                    "error": e.__cause__ if e.__cause__ else e.message,
                    "query": e.query,
                    "variables": e.variables,
                },
            )
            notify(message_body, "haie")
            raise e

        dossiers = data["demarche"]["dossiers"]
        has_next_page = dossiers.get("pageInfo", {}).get("hasNextPage", False)
        cursor = dossiers.get("pageInfo", {}).get("endCursor", None)

        return {
            "demarche": data["demarche"],
            "dossiers": dossiers["nodes"],
            "hasNextPage": has_next_page,
            "endCursor": cursor,
        }

    def _create_direct_upload(self, dossier_number, dossier_id, attachment_file):
        """Create direct upload related to a dossier"""

        # Only uploaded file in django allowed
        if not isinstance(attachment_file, UploadedFile):
            logger.error("File will not be sent, format not allowed")
            return None

        # Prepare input
        attachment_checksum = hashlib.file_digest(attachment_file, "md5").digest()
        attachment_checksum_b64 = b64encode(attachment_checksum).decode()
        content_type = guess_type(attachment_file.name)[0]
        variables = {
            "input": {
                "byteSize": attachment_file.size,
                "checksum": attachment_checksum_b64,
                "clientMutationId": "Envergo1234",
                "contentType": content_type,
                "dossierId": dossier_id,
                "filename": attachment_file.name,
            }
        }

        query = DOSSIER_CREATE_DIRECT_UPLOAD_MUTATION

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"{DS_DISABLED_BASE_MESSAGE}"
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            data = self._fake_execute(
                fake_dossier_filename="fake_dossier_send_message_attachment.json"
            )
        else:
            # Send query to create direct upload
            try:
                data = self.execute(query, variables)
            except DemarchesSimplifieesError as e:
                logger.error(
                    "Error when getting credentials to direct upload file to Demarches Simplifiees",
                    extra={
                        "dossier_number": dossier_number,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                message = render_to_string(
                    "haie/petitions/mattermost_demarches_simplifiees_api_error_dossier_send_message.txt",
                    context={
                        "dossier_number": dossier_number,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                notify(dedent(message), "haie")
                return None

            # On query success, put file to url
            if (
                "createDirectUpload" in data
                and "directUpload" in data["createDirectUpload"]
            ):
                credentials = data["createDirectUpload"]["directUpload"]
                credentials_headers = json.loads(credentials["headers"])

                try:
                    with attachment_file.open("rb") as payload:
                        response = requests.put(
                            credentials["url"],
                            data=payload,
                            headers=credentials_headers,
                        )
                except Exception as e:
                    logger.error(
                        f"Error when sending attachment file Demarches Simplifiees direct upload : {e}",
                        extra={
                            "dossier_number": dossier_number,
                        },
                    )
                    message = render_to_string(
                        "haie/petitions/mattermost_demarches_simplifiees_api_error_dossier_send_message.txt",
                        context={
                            "dossier_number": dossier_number,
                        },
                    )
                    notify(dedent(message), "haie")
                    return None

                if response.status_code == 201:
                    logger.info(
                        f"File successfully put to direct upload {attachment_file.name}"
                    )
                    return data["createDirectUpload"]["directUpload"]
                else:
                    logger.error(
                        f"Error on uploading {attachment_file.name}",
                        extra={
                            "dossier_number": dossier_number,
                            "query": query,
                            "variables": variables,
                        },
                    )
                    return None

            else:
                logger.error(
                    "Error with credentials for direct upload to Demarches Simplifiees",
                    extra={
                        "dossier_number": dossier_number,
                        "query": query,
                        "variables": variables,
                    },
                )
                return None

    def dossier_send_message(
        self,
        dossier_number,
        dossier_id,
        message_body,
        attachment_file=None,
        instructeur_id=None,
    ) -> dict:
        """Dossier send message query"""

        instructeur_id = settings.DEMARCHES_SIMPLIFIEES["INSTRUCTEUR_ID"]
        if not instructeur_id:
            logger.warning("Missing instructeur id.")
            return None
        if not dossier_id:
            logger.warning("Missing dossier id.")
            return None

        variables = {
            "input": {
                "dossierId": dossier_id,
                "instructeurId": instructeur_id,
                "body": message_body,
            }
        }

        # If attachments, upload files
        # TODO: send message with several files
        if attachment_file:
            if isinstance(attachment_file, list):
                if len(attachment_file) > 1:
                    logger.warning("Can't send multiple files. Use first")
                attachment_file = attachment_file[0]
            else:
                attachment_file = attachment_file

            attachment_uploaded = self._create_direct_upload(
                dossier_number, dossier_id, attachment_file
            )
            if attachment_uploaded is not None:
                variables["input"].update(
                    {"attachment": attachment_uploaded["signedBlobId"]}
                )

        # Send message
        query = DOSSIER_ENVOYER_MESSAGE_MUTATION

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"{DS_DISABLED_BASE_MESSAGE}"
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            data = self._fake_execute(
                fake_dossier_filename="fake_dossier_send_message.json"
            )
        else:
            try:
                data = self.execute(query, variables)
            except DemarchesSimplifieesError as e:
                logger.error(
                    "Error when sending message to Demarches Simplifiees",
                    extra={
                        "dossier_number": dossier_number,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                message = render_to_string(
                    "haie/petitions/mattermost_demarches_simplifiees_api_error_dossier_send_message.txt",
                    context={
                        "dossier_number": dossier_number,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                notify(dedent(message), "haie")
                return None

        query_name = "dossierEnvoyerMessage"

        # If message has not been sent because errors
        if query_name not in data or data[query_name]["errors"]:
            logger.error(
                "Error when sending message to Demarches Simplifiees",
                extra={
                    "response": data,
                    "query": query,
                    "variables": variables,
                },
            )
            message = render_to_string(
                "haie/petitions/mattermost_demarches_simplifiees_api_error_dossier_send_message.txt",
                context={
                    "dossier_number": dossier_number,
                    "error": data,
                    "query": query,
                    "variables": variables,
                },
            )
            notify(dedent(message), "haie")
            return None

        # Return query response content
        return data["dossierEnvoyerMessage"]

    def _change_dossier_state(
        self,
        project_reference,
        dossier_id,
        state,
        motivation: str,
        disable_notification: bool,
    ) -> dict | None:
        """Change dossier state. Use different query depending on target state

        returns: the query response containing the whole dossier that can be cached, or None if error
        """

        mapping = {
            DossierState.accepte: (DOSSIER_ACCEPTER_MUTATION, "dossierAccepter"),
            DossierState.en_construction: (
                DOSSIER_REPASSER_EN_CONSTRUCTION_MUTATION,
                "dossierRepasserEnConstruction",
            ),
            DossierState.en_instruction: (
                DOSSIER_PASSER_EN_INSTRUCTION_MUTATION,
                "dossierPasserEnInstruction",
            ),
            "back_to_instruction": (
                DOSSIER_REPASSER_EN_INSTRUCTION_MUTATION,
                "dossierRepasserEnInstruction",
            ),
            DossierState.refuse: (DOSSIER_REFUSER_MUTATION, "dossierRefuser"),
            DossierState.sans_suite: (
                DOSSIER_CLASSER_SANS_SUITE_MUTATION,
                "dossierClasserSansSuite",
            ),
        }

        query, result_key = mapping[state]
        variables = {
            "input": {
                "disableNotification": disable_notification,
                "dossierId": dossier_id,
            }
        }
        if motivation:
            variables["input"]["motivation"] = motivation

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"Use fake dossier if dossier is not draft."
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            with open(
                DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH / "fake_dossier.json",
                "r",
            ) as file:
                response = json.load(file)
                data = copy.deepcopy(response["data"])
                data["dossier"]["state"] = (
                    state.value
                    if state != "back_to_instruction"
                    else DossierState.en_instruction.value
                )
                data = {result_key: data, "errors": []}
        else:
            instructeur_id = settings.DEMARCHES_SIMPLIFIEES["INSTRUCTEUR_ID"]
            if not instructeur_id:
                raise DemarchesSimplifieesError(
                    query,
                    {},
                    "INSTRUCTEUR_ID is not set, please check the configuration.",
                )

            variables["input"]["instructeurId"] = instructeur_id

            try:
                data = self.execute(query, variables)
            except DemarchesSimplifieesError as e:
                logger.error(
                    "Error when changing dossier state via Demarches Simplifiees API",
                    extra={
                        "dossier_id": dossier_id,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                message = render_to_string(
                    "haie/petitions/mattermost_demarches_simplifiees_api_error_change_dossier_state.txt",
                    context={
                        "dossier_number": project_reference,
                        "error": e.__cause__ if e.__cause__ else e.message,
                        "query": e.query,
                        "variables": e.variables,
                    },
                )
                notify(dedent(message), "haie")
                return None

        # State change failed
        if (
            data.get("errors")
            or result_key not in data
            or data[result_key].get("errors")
        ):
            logger.error(
                "Error when changing dossier state via Demarches Simplifiees API",
                extra={
                    "response": data,
                    "query": query,
                    "variables": variables,
                },
            )
            message = render_to_string(
                "haie/petitions/mattermost_demarches_simplifiees_api_error_change_dossier_state.txt",
                context={
                    "dossier_number": project_reference,
                    "error": data,
                    "query": query,
                    "variables": variables,
                },
            )
            notify(dedent(message), "haie")
            return None

        # Return query response content containing the whole dossier that can be cached in the project reference
        return data[result_key]

    def accept_dossier(
        self,
        project_reference,
        dossier_id,
        motivation: str = None,
        disable_notification=True,
    ) -> dict | None:
        """Accept dossier

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            DossierState.accepte,
            motivation,
            disable_notification,
        )

    def pass_back_dossier_under_construction(
        self,
        project_reference,
        dossier_id,
        disable_notification=True,
    ) -> dict | None:
        """Pass back the dossier under construction

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            DossierState.en_construction,
            "",
            disable_notification,
        )

    def pass_dossier_to_instruction(
        self,
        project_reference,
        dossier_id,
        disable_notification=True,
    ) -> dict | None:
        """Pass the dossier to instruction

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            DossierState.en_instruction,
            "",
            disable_notification,
        )

    def pass_back_dossier_to_instruction(
        self,
        project_reference,
        dossier_id,
        disable_notification=True,
    ) -> dict | None:
        """Pass back the dossier to instruction

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            "back_to_instruction",
            "",
            disable_notification,
        )

    def refuse_dossier(
        self,
        project_reference,
        dossier_id,
        motivation: str,
        disable_notification=True,
    ) -> dict | None:
        """Pass the dossier to "refusé"

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            DossierState.refuse,
            motivation,
            disable_notification,
        )

    def close_dossier(
        self,
        project_reference,
        dossier_id,
        motivation: str,
        disable_notification=True,
    ) -> dict | None:
        """Pass the dossier to "classé sans suite"

        returns: the query response containing the whole dossier that can be cached, or None if error
        """
        return self._change_dossier_state(
            project_reference,
            dossier_id,
            DossierState.sans_suite,
            motivation,
            disable_notification,
        )


class DemarchesSimplifieesError(Exception):
    """Démarches Simplifiées client Exception"""

    def __init__(self, query: str = None, variables: dict = None, message: str = None):
        super().__init__(message)
        self.message = message
        self.query = query
        self.variables = variables
