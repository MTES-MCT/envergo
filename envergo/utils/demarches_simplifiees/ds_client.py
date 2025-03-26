import json
import logging
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import requests
from django.conf import settings
from django.template.loader import render_to_string

from envergo.petitions.tests.factories import DEMARCHES_SIMPLIFIEES_FAKE_DOSSIER
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


class NotEnabledException(Exception):
    pass


class DsClient:
    def __init__(self):
        self.pre_fill_api_url = settings.DEMARCHES_SIMPLIFIEES["PRE_FILL_API_URL"]
        self.token = settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_BEARER_TOKEN"]
        self.api_url = settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"]
        with open(
            Path(__file__).resolve().parent / "graphql" / "ds_queries.gql"
        ) as query_file:
            self.query = query_file.read()

    def launch_graphql_query(self, operation_name, variables=None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = {"query": self.query, "operationName": operation_name}
        if variables:
            data["variables"] = variables

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            raise NotEnabledException(
                f"Demarches Simplifiees is not enabled. Doing nothing."
                f"\nrequest.url: {self.api_url}"
                f"\nrequest.body: {data}"
            )
            return json.loads(DEMARCHES_SIMPLIFIEES_FAKE_DOSSIER)

        response = requests.post(self.api_url, json=data, headers=headers)

        logger.debug(
            f"""
                Demarches simplifiees API request status: {response.status_code}"
                * response.text: {response.text},
                * response.status_code: {response.status_code},
                * request.url: {self.api_url},
                * request.body: {data},
                """,
        )

        if response.status_code == 200:
            results = response.json()
            if "errors" in results.keys() and results.get("data", None) is None:
                logger.error(
                    results["errors"],
                    extra={
                        "response.text": response.text,
                        "response.status_code": response.status_code,
                        "request.url": self.api_url,
                        "request.body": data,
                    },
                )
                raise Exception(f"Query failed to run: {results['errors']}")
            return results
        else:
            logger.error(
                "Demarches simplifiees API request failed",
                extra={
                    "response.text": response.text,
                    "response.status_code": response.status_code,
                    "request.url": self.api_url,
                    "request.body": data,
                },
            )
            raise Exception(
                f"HTTP Error while running query. Status code: {response.status_code}. "
                f"Error: {response.text}"
            )

    def get_demarche(self, demarche_number) -> dict:
        """
        Get info about one demarche, without its dossiers.
        Use it to get the list of instructeurs and the list of fields with their ids.
        :param demarche_number: integer
        :return: json string
        """
        variables = {
            "demarcheNumber": demarche_number,
            "includeDossiers": False,
            "includeGroupeInstructeurs": True,
            "includeRevision": True,  # to list custom fields with their ids
        }
        return self.launch_graphql_query("getDemarche", variables=variables)

    def get_demarche_dossiers(self, demarche_number) -> Iterator[dict]:
        """
        Get all dossiers from one given demarche
        :param demarche_number:
        :return: iterator on all available dossiers of demarche
        """
        variables = {
            "demarcheNumber": demarche_number,
            "includeDossiers": True,
        }
        result = self.launch_graphql_query("getDemarche", variables=variables)
        yield from result["data"]["demarche"]["dossiers"]["nodes"]
        has_next_page = result["data"]["demarche"]["dossiers"]["pageInfo"][
            "hasNextPage"
        ]
        while has_next_page:
            end_cursor = result["data"]["demarche"]["dossiers"]["pageInfo"]["endCursor"]
            has_next_page = result["data"]["demarche"]["dossiers"]["pageInfo"][
                "hasNextPage"
            ]
            variables["after"] = end_cursor
            result = self.launch_graphql_query("getDemarche", variables=variables)
            yield from result["data"]["demarche"]["dossiers"]["nodes"]

    def get_dossier(self, dossier_number) -> dict:
        variables = {
            "dossierNumber": dossier_number,
        }
        results = {}

        try:
            results = self.launch_graphql_query("getDossier", variables)

        except NotEnabledException as e:
            logger.warning(e)
            return None

        except Exception as e:
            logger.error(e)
            message = render_to_string(
                "demarches_simplifiees/mattermost_demarches_simplifiees_api_error_one_dossier.txt",
                context={
                    "status_code": "?",
                    "response": results,
                    "api_url": self.api_url,
                    "body": "body",
                    "command": "get_dossier",
                },
            )
            notify(dedent(message), "haie")
            return None

        dossier = (results.get("data") or {}).get("dossier")

        if not dossier:
            logger.error(
                "Demarches simplifiees API response is not well formated.",
                extra={
                    "response.json": results,
                },
            )

            message = render_to_string(
                "demarches_simplifiees/mattermost_demarches_simplifiees_api_unexpected_format.txt",
                context={
                    "status_code": 200,
                    "response": results,
                    "api_url": self.api_url,
                    "body": "body",
                    "command": "get_dossier",
                },
            )
            notify(dedent(message), "haie")

            return None

        return dossier
