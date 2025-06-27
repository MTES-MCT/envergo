import json
import logging
from pathlib import Path
from textwrap import dedent

from django.conf import settings
from django.template.loader import render_to_string
from gql import Client, gql
from gql.transport.exceptions import TransportError
from gql.transport.requests import RequestsHTTPTransport
from graphql import GraphQLError

from envergo.petitions.demarches_simplifiees.models import Dossier
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


class DemarchesSimplifieesError(Exception):
    def __init__(self, query: str, variables: dict, message: str = None):
        super().__init__()
        self.message = message
        self.query = query
        self.variables = variables


class DemarchesSimplifieesClient:
    def __init__(self):
        self.transport = RequestsHTTPTransport(
            url=settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"],
            headers={
                "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEES['GRAPHQL_API_BEARER_TOKEN']}"
            },
        )
        self.client = Client(transport=self.transport, fetch_schema_from_transport=True)

    def execute(self, query_str: str, variables: dict = None):
        query = gql(query_str)
        try:
            result = self.client.execute(query, variable_values=variables or {})
        except (TransportError, GraphQLError) as e:
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

    def fetch_project_details(self, dossier_number) -> Dossier | None:
        variables = {"dossierNumber": dossier_number}
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

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning(
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"Use fake dossier if dossier is not draft."
                f"\nquery: {query}"
                f"\nvariables: {variables}"
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
                dossier = Dossier.from_dict(response["data"]["dossier"])
        else:
            try:
                data = self.execute(query, variables)
            except DemarchesSimplifieesError as e:
                if any(
                    error["extensions"]["code"] == "not_found"
                    and any(path == "dossier" for path in error["path"])
                    for error in e.__cause__.errors or []
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

            dossier = Dossier.from_dict(data["dossier"]) if "dossier" in data else None

        if dossier is None:
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

        return dossier
