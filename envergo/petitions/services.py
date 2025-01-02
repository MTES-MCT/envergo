import logging
from dataclasses import dataclass
from textwrap import dedent

import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse

from envergo.moulinette.models import ConfigHaie
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)


@dataclass
class AdditionalInfo:
    label: str
    value: str | int | float
    unit: str | None


@dataclass
class ItemDetails:
    result: bool
    details: list[AdditionalInfo]


@dataclass
class Item:
    label: str
    value: str | int | float | ItemDetails
    unit: str | None
    comment: str | None


@dataclass
class InstructorInformationDetails:
    label: str
    items: list[Item]


@dataclass
class InstructorInformation:
    slug: str | None
    label: str | None
    items: list[Item]
    details: list[InstructorInformationDetails]


def compute_instructor_informations(
    petition_project, moulinette
) -> list[InstructorInformation]:

    department = moulinette.catalog.get("department")  # department is mandatory
    config = ConfigHaie.objects.get(department__department=department)
    ds_details = fetch_project_details_from_demarches_simplifiees(
        petition_project.demarches_simplifiees_dossier_number, config
    )

    hedge_data = petition_project.hedge_data
    length_to_remove = hedge_data.length_to_remove()
    length_to_plant = hedge_data.length_to_plant()
    project_details = InstructorInformation(
        slug=None,
        label=None,
        items=[
            Item("Référence", petition_project.reference, None, None),
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_remove()),
                        None,
                        None,
                    ),
                    Item("Total linéaire détruit", length_to_remove, "m", None),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_plant()),
                        None,
                        None,
                    ),
                    Item("Total linéaire planté", length_to_plant, "m", None),
                    Item(
                        "Ratio en longueur",
                        (
                            round(length_to_plant / length_to_remove, 2)
                            if length_to_remove
                            else ""
                        ),
                        None,
                        "longueur plantée / longueur détruite",
                    ),
                ],
            ),
        ],
    )

    if ds_details:
        if ds_details.city:
            project_details.items.append(
                Item("Commune principale", ds_details.city, None, None)
            )
        if ds_details.applicant_name:
            project_details.items.append(
                Item("Nom du demandeur", ds_details.applicant_name, None, None)
            )

    lineaire_total = moulinette.catalog.get("lineaire_total", "")
    lineaire_detruit_pac = hedge_data.lineaire_detruit_pac()
    lineaire_plante_pac = hedge_data.lineaire_plante_pac()

    bcae8 = InstructorInformation(
        slug="bcae8",
        label="BCAE 8",
        items=[
            Item("Total linéaire exploitation déclaré", lineaire_total, "m", None),
            Item("Motif", moulinette.catalog.get("motif", ""), None, None),
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés sur parcelle PAC",
                        len(hedge_data.hedges_to_remove_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire détruit hors alignement d’arbres",
                        hedge_data.lineaire_detruit_pac(),
                        "m",
                        "Sur parcelle PAC, hors alignement d’arbres",
                    ),
                    Item(
                        "Pourcentage détruit / total linéaire",
                        (
                            round(lineaire_detruit_pac / lineaire_total * 100, 2)
                            if lineaire_total
                            else ""
                        ),
                        "%",
                        None,
                    ),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés plantés hors alignement d’arbres",
                        len(hedge_data.hedges_to_plant_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire planté",
                        hedge_data.lineaire_plante_pac(),
                        "m",
                        "Hors alignement d’arbres",
                    ),
                    Item(
                        "Ratio en longueur",
                        (
                            round(lineaire_plante_pac / lineaire_detruit_pac, 2)
                            if lineaire_detruit_pac > 0
                            else ""
                        ),
                        None,
                        "Longueur plantée / longueur détruite (prises hors alignements d’arbres)",
                    ),
                ],
            ),
        ],
    )

    if ds_details:
        if ds_details.pacage:
            bcae8.items.append(Item("N° PACAGE", ds_details.pacage, None, None))

    hedges_to_remove_near_pond = [
        h for h in hedge_data.hedges_to_remove() if h.proximite_mare
    ]
    hedges_to_plant_near_pond = [
        h for h in hedge_data.hedges_to_plant() if h.proximite_mare
    ]

    hedges_to_remove_woodland_connection = [
        h for h in hedge_data.hedges_to_remove() if h.connexion_boisement
    ]
    hedges_to_plant_woodland_connection = [
        h for h in hedge_data.hedges_to_plant() if h.connexion_boisement
    ]

    hedges_to_remove_under_power_line = [
        h for h in hedge_data.hedges_to_remove() if h.sous_ligne_electrique
    ]
    hedges_to_plant_under_power_line = [
        h for h in hedge_data.hedges_to_plant() if h.sous_ligne_electrique
    ]
    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        items=[
            Item(
                "Présence d'une mare à moins de 200 m",
                ItemDetails(
                    result=len(hedges_to_remove_near_pond) > 0
                    or len(hedges_to_plant_near_pond) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_near_pond))} m "
                            f"• {', '.join([h.id for h in hedges_to_remove_near_pond])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_near_pond))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_near_pond])}",
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Connexion à un boisement ou une haie",
                ItemDetails(
                    result=len(hedges_to_remove_woodland_connection) > 0
                    or len(hedges_to_plant_woodland_connection) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_woodland_connection))} m "
                            f"• {', '.join([h.id for h in hedges_to_remove_woodland_connection])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_woodland_connection))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_woodland_connection])}",
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Proximité ligne électrique",
                ItemDetails(
                    result=len(hedges_to_remove_under_power_line) > 0
                    or len(hedges_to_plant_under_power_line) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_under_power_line))} m "
                            f"• {', '.join([h.id for h in hedges_to_remove_under_power_line])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_under_power_line))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_under_power_line])}",
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
        ],
        details=[],
    )

    return [project_details, bcae8, ep]


@dataclass
class ProjectDetails:
    applicant_name: str | None
    city: str | None
    pacage: str | None


def fetch_project_details_from_demarches_simplifiees(
    dossier_number, config
) -> ProjectDetails | None:

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
        current_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        admin_url = reverse(
            "admin:moulinette_confighaie_change",
            args=[config.id],
        )
        message = f"""\
        ### Récupération des informations d'un dossier depuis Démarches-simplifiées : :x: erreur

        Les identifiants des champs PACAGE et Commune principale ne sont pas renseignés
        dans la configuration du département {config.department.department}.

        [Admin django](https://{current_site.domain}{admin_url})
        """
        notify(dedent(message), "haie")
        return None

    api_url = settings.DEMARCHES_SIMPLIFIEE["GRAPHQL_API_URL"]
    variables = f"""{{
              "dossierNumber":{dossier_number}
            }}"""
    query = """query getDossier($dossierNumber: Int!) {{
          dossier(number: $dossierNumber) {{
            id
            number
            state
            usager {{
              email
            }}
            demandeur {{
              ... on PersonnePhysique {{
                civilite
                nom
                prenom
                email
              }}
            }}
            champs {{
              id
              stringValue
            }}
          }}
        }}"""

    body = {
        "query": query,
        "variables": variables,
    }
    response = requests.post(
        api_url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEMARCHES_SIMPLIFIEE['GRAPHQL_API_BEARER_TOKEN']}",
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
### Récupération des informations d'un dossier depuis Démarches-simplifiées : :x: erreur

L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier n°{dossier_number}.

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
"""
        notify(dedent(message), "haie")
        return None

    data = response.json() or {}

    dossier = (data.get("data") or {}).get("dossier")

    if dossier is None:
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
### Récupération des informations d'un dossier depuis Démarches-simplifiées : :warning: anomalie

La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu. Le dossier concerné n'a pas été récupéré.

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

"""
        notify(dedent(message), "haie")
        return None
    applicant = dossier.get("demandeur") or {}
    applicant_name = f"{applicant.get('civilite', '')} {applicant.get('prenom', '')} {applicant.get('nom', '')}"
    applicant_name = (
        None
        if applicant_name is None or applicant_name.strip() == ""
        else applicant_name
    )
    city = None
    pacage = None
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

    return ProjectDetails(applicant_name, city, pacage)
