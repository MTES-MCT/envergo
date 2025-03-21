from copy import copy

import factory
from factory.django import DjangoModelFactory

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.petitions.models import DOSSIER_STATES, PetitionProject

DEMARCHES_SIMPLIFIEES_FAKE = {
    "ENABLED": True,
    "PRE_FILL_API_URL": "https://www.demarches-simplifiees.example.com/api/public/v1/",
    "GRAPHQL_API_URL": "https://www.demarches-simplifiees.example.com/api/v2/graphql",
    "GRAPHQL_API_BEARER_TOKEN": None,
    "DOSSIER_DOMAIN_BLACK_LIST": [],
}

DEMARCHES_SIMPLIFIEES_FAKE_DISABLED = copy(DEMARCHES_SIMPLIFIEES_FAKE)
DEMARCHES_SIMPLIFIEES_FAKE_DISABLED["ENABLED"] = False

DEMARCHES_SIMPLIFIEES_FAKE_DOSSIER = """{
    "id": "RG9zc2llci0yMjE5ODcwNg==",
    "number": 22198706,
    "state": "en_instruction",
    "usager": {
        "email": "jane.doe@beta.gouv.fr"
    },
    "demandeur": {
        "civilite": "M",
        "nom": "Doe",
        "prenom": "Jane",
        "email": null
    },
    "champs": [
        {
            "id": "Q2hhbXAtNDUzNDEzNQ==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDcyOTE3MA==",
            "stringValue": "Agriculteur, agricultrice"
        },
        {
            "id": "Q2hhbXAtNDcyOTE3MQ==",
            "stringValue": "Jane Avena"
        },
        {
            "id": "Q2hhbXAtNDUzNDE0NA==",
            "stringValue": "Saint-Nicolas-aux-Bois (02410)"
        },
        {
            "id": "Q2hhbXAtNDUzNDE0NQ==",
            "stringValue": "jane.doe@beta.gouv.fr"
        },
        {
            "id": "Q2hhbXAtNDU0MzkzMg==",
            "stringValue": "06 12 34 56 78"
        },
        {
            "id": "Q2hhbXAtNDU0MzkzOA==",
            "stringValue": "123456789"
        },
        {
            "id": "Q2hhbXAtNDUzNDE1Ng==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDc0NDcyMQ==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDU0Mzk0Mw==",
            "stringValue": "https://haie.beta.gouv.fr/projet/26KRPM/consultation/"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4Nw==",
            "stringValue": "Saint-Nicolas-aux-Bois (02410)"
        },
        {
            "id": "Q2hhbXAtNDUzNDE0Ng==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE3NQ==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE3Ng==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE3Nw==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4OA==",
            "stringValue": null
        },
        {
            "id": "Q2hhbXAtNDcyOTE3OA==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDcyOTE3OQ==",
            "stringValue": "false"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4MA==",
            "stringValue": null
        },
        {
            "id": "Q2hhbXAtNDU5NjU1Mw==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDcyOTI4NA==",
            "stringValue": "true"
        },
        {
            "id": "Q2hhbXAtNDU1OTU2Mw==",
            "stringValue": "Transfert de parcelles"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4NQ==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4Ng==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTE4OQ==",
            "stringValue": null
        },
        {
            "id": "Q2hhbXAtNTAwNzQ1Mw==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDU5NjU2NA==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDg3NjQ5Nw==",
            "stringValue": "Dérogation"
        },
        {
            "id": "Q2hhbXAtNDg3NjUxNQ==",
            "stringValue": "L'inventaire ciblé n'est pas nécessaire"
        },
        {
            "id": "Q2hhbXAtNDg3NjUyNQ==",
            "stringValue": null
        },
        {
            "id": "Q2hhbXAtNDcyOTIwMQ==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDU5Nzc0Mw==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIwMg==",
            "stringValue": "Entre 25 et 50 ans"
        },
        {
            "id": "Q2hhbXAtNDcyOTIwMw==",
            "stringValue": "true"
        },
        {
            "id": "Q2hhbXAtNDcyOTI4Mg==",
            "stringValue": "false"
        },
        {
            "id": "Q2hhbXAtNDcyOTIwNA==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIwNQ==",
            "stringValue": null
        },
        {
            "id": "Q2hhbXAtNDcyOTIwNg==",
            "stringValue": "false"
        },
        {
            "id": "Q2hhbXAtNDcyOTIwOQ==",
            "stringValue": "true"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxMA==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxMQ==",
            "stringValue": "Une fois par an"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxMg==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxMw==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDcyOTIxNA==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxNQ==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxNg==",
            "stringValue": "false"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxOA==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIxOQ==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIyMA==",
            "stringValue": "test"
        },
        {
            "id": "Q2hhbXAtNDcyOTIyMQ==",
            "stringValue": "false"
        },
        {
            "id": "Q2hhbXAtNDU1OTU0Nw==",
            "stringValue": ""
        },
        {
            "id": "Q2hhbXAtNDcyOTIyNA==",
            "stringValue": "true"
        },
        {
            "id": "Q2hhbXAtNDcyOTI4Mw==",
            "stringValue": "true"
        }
    ]
}"""


class PetitionProjectFactory(DjangoModelFactory):
    class Meta:
        model = PetitionProject

    reference = "ABC123"
    moulinette_url = (
        "http://haie.local:3000/simulateur/resultat/?profil=autre&motif=autre&reimplantation=non"
        "&haies=4406e311-d379-488f-b80e-68999a142c9d&department=44&travaux=destruction&element=haie"
    )
    hedge_data = factory.SubFactory(HedgeDataFactory)
    demarches_simplifiees_dossier_number = 21059675
    demarches_simplifiees_state = DOSSIER_STATES.draft
