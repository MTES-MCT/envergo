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
    "annotations": [
    {
        "champDescriptorId": "champDescriptorId",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
        "label": "label",
        "prefilled": true,
        "stringValue": "stringValue",
        "updatedAt": "2025-03-18T14:31:05.359Z"
    }
    ],
    "archived": true,
    "attestation": {
    "byteSize": 42,
    "byteSizeBigInt": "9007199254740991",
    "checksum": "checksum",
    "contentType": "contentType",
    "createdAt": "2025-03-18T14:31:05.359Z",
    "filename": "filename",
    "url": "https://website.com"
    },
    "avis": [
    {
        "dateQuestion": "2025-03-18T14:31:05.359Z",
        "dateReponse": "2025-03-18T14:31:05.359Z",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
        "question": "question",
        "questionAnswer": true,
        "questionLabel": "questionLabel",
        "reponse": "reponse"
    }
    ],
    "champs": [
    {
        "champDescriptorId": "champDescriptorId",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
        "label": "label",
        "prefilled": true,
        "stringValue": "stringValue",
        "updatedAt": "2025-03-18T14:31:05.359Z"
    }
    ],
    "connectionUsager": "deleted",
    "dateDepot": "2025-03-18T14:31:05.359Z",
    "dateDerniereCorrectionEnAttente": "2025-03-18T14:31:05.359Z",
    "dateDerniereModification": "2025-03-18T14:31:05.359Z",
    "dateDerniereModificationAnnotations": "2025-03-18T14:31:05.359Z",
    "dateDerniereModificationChamps": "2025-03-18T14:31:05.359Z",
    "dateExpiration": "2025-03-18T14:31:05.359Z",
    "datePassageEnConstruction": "2025-03-18T14:31:05.359Z",
    "datePassageEnInstruction": "2025-03-18T14:31:05.359Z",
    "datePrevisionnelleDecisionSVASVR": "2025-03-18T14:31:05.359Z",
    "dateSuppressionParAdministration": "2025-03-18T14:31:05.359Z",
    "dateSuppressionParUsager": "2025-03-18T14:31:05.359Z",
    "dateTraitement": "2025-03-18T14:31:05.359Z",
    "dateTraitementSVASVR": "2025-03-18T14:31:05.359Z",
    "demandeur": {
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e"
    },
    "demarche": {
    "cadreJuridiqueURL": "cadreJuridiqueURL",
    "cadreJuridiqueUrl": "cadreJuridiqueUrl",
    "dateCreation": "2025-03-18T14:31:05.359Z",
    "dateDepublication": "2025-03-18T14:31:05.359Z",
    "dateDerniereModification": "2025-03-18T14:31:05.359Z",
    "dateFermeture": "2025-03-18T14:31:05.359Z",
    "datePublication": "2025-03-18T14:31:05.359Z",
    "declarative": "accepte",
    "demarcheURL": "https://website.com",
    "demarcheUrl": "https://website.com",
    "description": "A description",
    "dpoURL": "dpoURL",
    "dpoUrl": "dpoUrl",
    "dureeConservationDossiers": 42,
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
    "noticeURL": "https://website.com",
    "noticeUrl": "https://website.com",
    "number": 42,
    "opendata": true,
    "siteWebURL": "siteWebURL",
    "siteWebUrl": "siteWebUrl",
    "state": "brouillon",
    "tags": [
        "tags"
    ],
    "title": "title",
    "zones": [
        "zones"
    ]
    },
    "deposeParUnTiers": true,
    "geojson": {
    "byteSize": 42,
    "byteSizeBigInt": "9007199254740991",
    "checksum": "checksum",
    "contentType": "contentType",
    "createdAt": "2025-03-18T14:31:05.359Z",
    "filename": "filename",
    "url": "https://website.com"
    },
    "groupeInstructeur": {
    "closed": true,
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
    "label": "label",
    "number": 42
    },
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
    "instructeurs": [
    {
        "email": "test-email@yourcompany.com",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e"
    }
    ],
    "labels": [
    {
        "color": "beige_gris_galet",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
        "name": "A name"
    }
    ],
    "messages": [
    {
        "body": "body",
        "createdAt": "2025-03-18T14:31:05.359Z",
        "discardedAt": "2025-03-18T14:31:05.359Z",
        "email": "test-email@yourcompany.com",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e"
    }
    ],
    "motivation": "motivation",
    "motivationAttachment": {
    "byteSize": 42,
    "byteSizeBigInt": "9007199254740991",
    "checksum": "checksum",
    "contentType": "contentType",
    "createdAt": "2025-03-18T14:31:05.359Z",
    "filename": "filename",
    "url": "https://website.com"
    },
    "nomMandataire": "nomMandataire",
    "number": 42,
    "pdf": {
    "byteSize": 42,
    "byteSizeBigInt": "9007199254740991",
    "checksum": "checksum",
    "contentType": "contentType",
    "createdAt": "2025-03-18T14:31:05.359Z",
    "filename": "filename",
    "url": "https://website.com"
    },
    "prefilled": true,
    "prenomMandataire": "prenomMandataire",
    "revision": {
    "dateCreation": "2025-03-18T14:31:05.359Z",
    "datePublication": "2025-03-18T14:31:05.359Z",
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e"
    },
    "state": "accepte",
    "traitements": [
    {
        "dateTraitement": "2025-03-18T14:31:05.359Z",
        "emailAgentTraitant": "emailAgentTraitant",
        "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e",
        "motivation": "motivation",
        "state": "accepte"
    }
    ],
    "usager": {
    "email": "test-email@yourcompany.com",
    "id": "08a16b83-9094-4e89-8c05-2ccadd5c1c7e"
    }
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
