import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from django.conf import settings
from django.template.loader import render_to_string
from gql import Client, gql
from gql.transport.exceptions import TransportError
from gql.transport.requests import RequestsHTTPTransport
from graphql import GraphQLError

from envergo.petitions.demarches_simplifiees.models import DemarcheWithRawDossiers
from envergo.petitions.demarches_simplifiees.queries import (
    DOSSIER_ENVOYER_MESSAGE_MUTATION,
    GET_DOSSIER_MESSAGES_QUERY,
    GET_DOSSIER_QUERY,
    GET_DOSSIERS_FOR_DEMARCHE_QUERY,
)
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH = Path(
    settings.APPS_DIR / "petitions" / "demarches_simplifiees" / "data"
)


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

    def execute(self, query_str: str, variables: dict = None):
        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            raise NotImplementedError("Démaches simplifiées is not enabled")

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
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"Use fake dossier if dossier is not draft."
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            with open(
                DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH / fake_dossier_filename,
                "r",
            ) as file:
                response = json.load(file)
                data = copy.deepcopy(response["data"])
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

    def dossier_send_message(
        self, dossier_number, dossier_id, message_body, instructeur_id=None
    ) -> dict:
        """Dossier send message query"""

        instructeur_id = settings.DEMARCHES_SIMPLIFIEES["INSTRUCTEUR_ID"]
        if not instructeur_id:
            logger.warning("Missing instructeur id.")
            return None

        variables = {
            "input": {
                "dossierId": dossier_id,
                "instructeurId": instructeur_id,
                "body": message_body,
            }
        }

        query = DOSSIER_ENVOYER_MESSAGE_MUTATION

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"Use fake dossier if dossier is not draft."
                f"\nquery: {query}"
                f"\nvariables: {variables}"
            )
            with open(
                DEMARCHES_SIMPLIFIEES_FAKE_DATA_PATH / "fake_dossier_send_message.json",
                "r",
            ) as file:
                response = json.load(file)
                data = copy.deepcopy(response["data"])
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
                    logger.error(
                        "Error when sending message to Demarches Simplifiees",
                        extra={
                            "dossier_number": dossier_number,
                            "error": e.__cause__ if e.__cause__ else e.message,
                            "query": e.query,
                            "variables": e.variables,
                        },
                    )
                else:
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
        if query_name not in data:
            logger.error(
                "Error when sending message to Demarches Simplifiees",
                extra={
                    "response": data,
                    "query": query,
                    "variables": variables,
                },
            )
            return None

        # Return query response content
        return data["dossierEnvoyerMessage"]


class DemarchesSimplifieesError(Exception):
    """Démarches Simplifiées client Exception"""

    def __init__(self, query: str, variables: dict, message: str = None):
        super().__init__()
        self.message = message
        self.query = query
        self.variables = variables
