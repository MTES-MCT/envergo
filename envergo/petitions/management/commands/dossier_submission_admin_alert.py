import logging
from datetime import datetime, timedelta
from textwrap import dedent

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.moulinette.models import ConfigHaie
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify
from envergo.utils.urls import extract_param_from_url

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch freshly submitted dossier on Démarches Simplifiées and notify admins."

    def handle(self, *args, **options):
        # get all the dossier updated in the last hour
        api_url = settings.DEMARCHES_SIMPLIFIEE["GRAPHQL_API_URL"]
        now_utc = datetime.utcnow()
        # NB: if you change this timedelta, you should also change the cron job frequency
        one_hour_ago_utc = now_utc - timedelta(hours=1)
        iso8601_one_hour_ago = one_hour_ago_utc.isoformat() + "Z"

        handled_demarches = []

        for activated_department in ConfigHaie.objects.filter(
            is_activated=True, demarche_simplifiee_number__isnull=False
        ).all():
            demarche_number = activated_department.demarche_simplifiee_number
            if demarche_number in handled_demarches:
                continue

            has_next_page = True
            cursor = None
            while has_next_page:

                variables = f"""{{
                      "demarcheNumber":{demarche_number},
                      "updatedSince": "{iso8601_one_hour_ago}",
                      "after":"{cursor if cursor else "null"}"
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
                                }
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
                        "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEE["GRAPHQL_API_BEARER_TOKEN"]}",
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
                    ### Récupération des status des dossiers depuis Démarches-simplifiées : :x: erreur

                    L'API de Démarches Simplifiées a retourné une erreur lors de la récupération des dossiers de \
                    la démarche n°{demarche_number}.

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

                    Cette requête est lancée automatiquement par la commande dossier_submission_admin_alert.
                    """
                    notify(dedent(message), "haie")
                    break

                data = response.json()

                dossiers = (
                    data.get("data", {})
                    .get("demarche", {})
                    .get("dossiers", {})
                    .get("nodes", None)
                )
                if dossiers is None:
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
                    ### Récupération des status des dossiers depuis Démarches-simplifiées : :warning: anomalie

                    La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu. Le status des \
                    dossiers concernés n'a pas pu être récupéré.

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

                    Cette requête est lancée automatiquement par la commande dossier_submission_admin_alert.
                    """
                    notify(dedent(message), "haie")
                    break

                has_next_page = (
                    data["data"]["demarche"]["dossiers"]
                    .get("pageInfo", {})
                    .get("hasNextPage", False)
                )
                cursor = (
                    data["data"]["demarche"]["dossiers"]
                    .get("pageInfo", {})
                    .get("endCursor", None)
                )

                for dossier in dossiers:
                    dossier_number = dossier["number"]
                    project = PetitionProject.objects.filter(
                        demarches_simplifiees_dossier_number=dossier_number
                    ).first()
                    if project is None:
                        logger.warning(
                            "A demarches simplifiees dossier has no corresponding project, it may have been "
                            "created without the guh",
                            extra={
                                "dossier_number": dossier_number,
                                "demarche_number": demarche_number,
                            },
                        )

                        message = f"""\
                        ### Récupération des status des dossiers depuis Démarches-simplifiées : :warning: anomalie

                        Un dossier Démarches Simplifiées concernant la démarche n°{demarche_number} n'a pas de projet \
                        associé.
                        Cela peut être dû à une création manuelle du dossier sans passer par la plateforme GUH.
                        Dossier concerné:
                        ```
                        {dossier}
                        ```


                        Cette requête est lancée automatiquement par la commande dossier_submission_admin_alert.
                        """
                        notify(dedent(message), "haie")
                        continue

                    if project.demarches_simplifiees_state is None:
                        # first time we have some data about this dossier
                        department = extract_param_from_url(
                            project.moulinette_url, "department"
                        )

                        ds_url = (
                            f"https://www.demarches-simplifiees.fr/procedures/{demarche_number}/dossiers/"
                            f"{dossier_number}"
                        )
                        admin_url = reverse(
                            "admin:petitions_petitionproject_change",
                            args=[project.reference],
                        )
                        message = f"""\
                            ### Nouveau dossier GUH {dict(DEPARTMENT_CHOICES).get(department, department)}
                            [Démarches simplifiées]({ds_url})
                            [Admin django](https://haie.beta.gouv.fr/{admin_url})
                            —
                            Linéaire détruit : {project.hedge_data.length_to_remove()} m
                            —
                            """

                        notify(dedent(message), "haie")

                    project.demarches_simplifiees_state = dossier["state"]
                    project.save()

            handled_demarches.append(demarche_number)
