import factory
from factory.django import DjangoModelFactory

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.petitions.models import DOSSIER_STATES, PetitionProject


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
