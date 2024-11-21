from textwrap import dedent

import requests
from django.core.management.base import BaseCommand
from django.urls import reverse

from envergo.moulinette.models import ConfigHaie
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify
from envergo.utils.urls import extract_param_from_url


class Command(BaseCommand):
    help = "Fetch freshly submitted dossier on Démarches Simplifiées and notify admins."

    def handle(self, *args, **options):
        api_url = "https://www.demarches-simplifiees.fr/api/v2/graphql"

        handled_demarches = []

        for activated_department in ConfigHaie.objects.filter(is_activated=True).all():
            demarche_number = activated_department.demarche_number
            if demarche_number in handled_demarches:
                continue

            project_field_id = next(
                (
                    field
                    for field in activated_department.demarche_simplifiee_pre_fill_config
                    if field["source"] == "project_reference"
                ),
                None,
            )
            if project_field_id is None:
                raise  # TODO

            has_next_page = True
            cursor = None
            while has_next_page:

                variables = f"""{{
                      "demarcheNumber":{demarche_number},
                      "state":"en_construction",
                      "updatedSince": {"2024-11-19T11:23:00+01:00"},
                      "after":{cursor if cursor else "null"}
                    }}"""  # TODO date

                query = """
                query getDemarche(
                    $demarcheNumber: Int!,
                    $state: DossierState,
                    $updatedSince: ISO8601DateTime,
                    $after: String
                    )
                 {
                    demarche(number: $demarcheNumber)
                    {
                        title
                        number
                        dossiers(
                            state: $state
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
                                    champs{
                                        id
                                        label
                                        stringValue
                                        prefilled
                                    }
                                }
                            }
                    }
                }"""

                response = requests.post(
                    api_url,
                    json={"query": query, "variables": variables},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer MzE3ZmQ1ZTQtOGYwMC00ZjU5LTk2OGMtZGU1NDEyNWIyYmQ3OzFjM1ZOTUx"
                        "TYjk5eWJSS2NKYWVweDJneg==",  # TODO
                    },
                )

                data = response.json()

                dossiers = (
                    data.get("data", {})
                    .get("demarche", {})
                    .get("dossiers", {})
                    .get("nodes", None)
                )
                if dossiers is None:
                    raise  # TODO

                has_next_page = (
                    data.get["data"]["demarche"]["dossiers"]
                    .get("pageInfo", {})
                    .get("hasNextPage", False)
                )
                cursor = (
                    data.get["data"]["demarche"]["dossiers"]
                    .get("pageInfo", {})
                    .get("endCursor", None)
                )

                for dossier in dossiers:
                    dossier_number = dossier["number"]
                    project_field = next(
                        (
                            champ
                            for champ in dossier["champs"]
                            if champ["id"] == project_field_id
                        ),
                        None,
                    )
                    if project_field is None:
                        raise  # TODO

                    if not project_field["prefilled"]:
                        raise  # TODO

                    project_reference = project_field["stringValue"]

                    project = PetitionProject.objects.filter(
                        reference=project_reference
                    ).first()
                    if project is None:
                        raise  # TODO

                    department = extract_param_from_url(
                        project.moulinette_url, "department"
                    )

                    ds_url = (
                        f"https://www.demarches-simplifiees.fr/procedures/{demarche_number}/dossiers/"
                        f"{dossier_number}"
                    )  # TODO
                    admin_url = reverse(
                        "admin:petitions_petitionproject_change",
                        args=[project_reference],
                    )
                    message = dedent(
                        f"""\
                        ## Nouveau dossier GUH {department}
                        [Démarches simplifiées]({ds_url})
                        [Admin django](https://haie.beta.gouv.fr/{admin_url})
                        —
                        Linéaire détruit : {project.hedge_data.length_to_remove()} m
                        —
                        """
                    )
                    notify(message, "haie")

            handled_demarches.append(demarche_number)
