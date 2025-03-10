import datetime
import logging
from textwrap import dedent

import requests
from django.settings import DEMARCHES_SIMPLIFIEES
from django.template.loader import render_to_string

from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


class DemarchesSimplifieesRequestManager:
    """Class to process queries to demarches-simplifiees.fr web API"""

    def __init__(self):
        self.pre_fill_api_url = f"{DEMARCHES_SIMPLIFIEES['PRE_FILL_API_URL']}"
        self.graphql_api_url = DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"]
        self.graphql_api_bearer_token = DEMARCHES_SIMPLIFIEES[
            "GRAPHQL_API_BEARER_TOKEN"
        ]
        self.dossier_domain_black_list = DEMARCHES_SIMPLIFIEES[
            "DOSSIER_DOMAIN_BLACK_LIST"
        ]

    def pre_fill_demarche(self, body, demarche_number):
        """Send a http request to pre-fill a dossier on demarches-simplifiees.fr

        Return the url of the created dossier if successful, None otherwise
        """
        api_url = f"{self.pre_fill_api_url}demarches/{demarche_number}/dossiers"

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
        return redirect_url, dossier_number

    def post_demarches_simplifiees_graphql_api(self, body, params=None):
        """Post a request to Démarche Simplifiées"""

        api_url = self.graphql_api_url
        response = requests.post(
            api_url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.graphql_api_bearer_token}",
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
            return None

        return response

    def fetch_demarche_projects_list(self, demarche_number):
        """Fetch démarche project list from demarches-simplifiees.fr"""
        # get all the dossier updated in the last hour
        now_utc = datetime.datetime.now(datetime.UTC)
        # NB: if you change this timedelta, you should also change the cron job frequency
        # The cron job is run every hour.
        # We fetch the updates from the last 2 hours to be sure as we may have some delay in the cron job execution
        two_hours_ago_utc = now_utc - datetime.timedelta(hours=2)
        iso8601_two_hours_ago = two_hours_ago_utc.isoformat()

        has_next_page = True
        cursor = None
        while has_next_page:

            variables = f"""{{
                    "demarcheNumber":{demarche_number},
                    "updatedSince": "{iso8601_two_hours_ago}",
                    "after":{f'"{cursor}"' if cursor else "null"}
                }}"""

            query = """
            query getDemarche(
                $demarcheNumber: Int!,
                $updatedSince: ISO8601DateTime,
                $after: String
                )
                {
                demarche(number: $demarcheNumber)
                {
                    title
                    number
                    dossiers(
                        updatedSince: $updatedSince
                        after: $after
                        )
                        {
                            pageInfo {
                                hasNextPage
                                endCursor
                            }
                            nodes {
                                number
                                state
                                usager {
                                    email
                                    }
                                champs{
                                    id
                                    stringValue
                                }
                            }
                        }
                }
            }"""
            body = {
                "query": query,
                "variables": variables,
            }
            response = self.post_demarches_simplifiees_graphql_api(body)

            if response.status_code >= 400:
                message_body = render_to_string(
                    "haie/petitions/mattermost_demarches_simplifiees_api_error.txt",
                    context={
                        "demarche_number": demarche_number,
                        "status_code": response.status_code,
                        "response": response.text,
                        "api_url": response.url,
                        "body": body,
                    },
                )
                notify(message_body, "haie")
                break

    def fetch_project_details(self, dossier_number):
        """Fetch project details from demarches-simplifiees.fr"""

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
        response = self.post_demarches_simplifiees(body=body)

        if response.status_code >= 400:

            message = f"""\
### Récupération des informations d'un dossier depuis Démarches-simplifiées : :x: erreur

L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier n°{dossier_number}.

Réponse de Démarches Simplifiées : {response.status_code}
```
{response.text}
```

Requête envoyée :
* Url: {response.url}
* Body:
```
{body}
```
"""
            notify(dedent(message), "haie")

        return response
