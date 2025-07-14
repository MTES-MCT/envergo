import datetime
import logging

import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from envergo.moulinette.models import ConfigHaie
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)

DOMAIN_BLACK_LIST = settings.DEMARCHES_SIMPLIFIEES["DOSSIER_DOMAIN_BLACK_LIST"]


class Command(BaseCommand):
    help = "Fetch freshly submitted dossier on Démarches Simplifiées and notify admins."

    def handle(self, *args, **options):
        """get all the dossier updated in the last hour"""

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning("Demarches Simplifiees is not enabled. Doing nothing.")
            return None

        api_url = settings.DEMARCHES_SIMPLIFIEES["GRAPHQL_API_URL"]
        now_utc = datetime.datetime.now(datetime.UTC)
        # NB: if you change this timedelta, you should also change the cron job frequency
        # The cron job is run every hour.
        # We fetch the updates from the last 2 hours to be sure as we may have some delay in the cron job execution
        two_hours_ago_utc = now_utc - datetime.timedelta(hours=2)
        iso8601_two_hours_ago = two_hours_ago_utc.isoformat()

        current_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        handled_demarches = []

        logging.info(f"Get DS files updated since {iso8601_two_hours_ago}")

        # As long as a demarche number is set, we run the sync
        # (event if the dept is not activated yet)
        departments_with_ds = ConfigHaie.objects.filter(
            demarche_simplifiee_number__isnull=False
        )
        for activated_department in departments_with_ds:
            demarche_number = activated_department.demarche_simplifiee_number

            logging.info(f"Handling demarche {demarche_number} ({activated_department}")

            if demarche_number in handled_demarches:
                continue

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
                                    dateDepot
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

                    message_body = render_to_string(
                        "haie/petitions/mattermost_demarches_simplifiees_api_error.txt",
                        context={
                            "demarche_number": demarche_number,
                            "status_code": response.status_code,
                            "response": response.text,
                            "api_url": api_url,
                            "body": body,
                        },
                    )
                    notify(message_body, "haie")
                    break

                data = response.json() or {}

                dossiers = (
                    ((data.get("data") or {}).get("demarche") or {}).get("dossiers")
                    or {}
                ).get("nodes", None)

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
                    message_body = render_to_string(
                        "haie/petitions/mattermost_demarches_simplifiees_api_unexpected_format.txt",
                        context={
                            "status_code": response.status_code,
                            "response": response.text,
                            "api_url": api_url,
                            "body": body,
                            "command": "dossier_submission_admin_alert",
                        },
                    )
                    notify(message_body, "haie")
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
                demarche_name = data["data"]["demarche"].get("title", "Nom inconnu")
                demarche_label = f"la démarche n°{demarche_number} ({demarche_name})"
                for dossier in dossiers:
                    dossier_number = dossier["number"]
                    project = PetitionProject.objects.filter(
                        demarches_simplifiees_dossier_number=dossier_number
                    ).first()

                    ds_url = (
                        f"https://www.demarches-simplifiees.fr/procedures/{demarche_number}/dossiers/"
                        f"{dossier_number}"
                    )
                    if project is None:
                        self.handle_unlinked_dossier(
                            dossier,
                            demarche_number,
                            demarche_name,
                            ds_url,
                            activated_department.demarches_simplifiees_project_url_id,
                        )
                        continue

                    project.synchronize_with_demarches_simplifiees(
                        dossier, current_site, demarche_label, ds_url
                    )

            handled_demarches.append(demarche_number)

    def handle_unlinked_dossier(
        self, dossier, demarche_number, demarche_name, ds_url, project_url_id
    ):
        """Handle a dossier that is not linked to any project in the database

        This dossier is not linked to any project on this environment
        it may have been created on another environment
        or it may have been created from scratch without the guh
        or it may be a duplicate of a GUH created dossier
        we will try to find out and apply a notification strategy
        """
        project_url = next(
            (
                champ["stringValue"]
                for champ in dossier["champs"]
                if champ["id"] == project_url_id
            ),
            "",
        )

        if any(domain in project_url for domain in DOMAIN_BLACK_LIST):
            # project url is from a blacklisted domain, it should have been created in another environment
            logger.warning(
                "A demarches simplifiees dossier has no corresponding project, it was probably "
                "created on another environment",
                extra={
                    "dossier_number": dossier["number"],
                    "demarche_number": demarche_number,
                    "project_url": project_url,
                },
            )
        else:
            # Either this dossier has been created in this environment but do not match an existing project,
            # or it has been created in a heterodox way.
            logger.warning(
                "A demarches simplifiees dossier has no corresponding project, it may have been "
                "created without the guh",
                extra={
                    "dossier_number": dossier["number"],
                    "demarche_number": demarche_number,
                    "project_url": project_url,
                },
            )
            message_body = render_to_string(
                "haie/petitions/mattermost_unlinked_dossier_notif.txt",
                context={
                    "demarche_name": demarche_name,
                    "ds_url": ds_url,
                    "dossier_number": dossier["number"],
                },
            )
            notify(message_body, "haie")
