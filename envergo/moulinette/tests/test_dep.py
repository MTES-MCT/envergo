import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def dep_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="dep")
    criteria = [
        CriterionFactory(
            title="Dérogation espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.dep.DerogationEspecesProtegees",
            activation_map=france_map,
        ),
    ]
    return criteria


def test_dep_is_soumis():
    ConfigHaieFactory()
    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "department": "44",
    }
    for motif_choice in [
        "transfert_parcelles",
        "chemin_acces",
        "meilleur_emplacement",
        "amenagement",
        "autre",
    ]:
        for reimplantation_choice in ["remplacement", "compensation", "non"]:
            data["motif"] = motif_choice
            data["reimplantation"] = reimplantation_choice
            moulinette = MoulinetteHaie(data, data, False)
            assert moulinette.is_evaluation_available()
            assert moulinette.result == "soumis", (
                motif_choice,
                reimplantation_choice,
            )
