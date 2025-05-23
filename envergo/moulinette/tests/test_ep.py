import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.services import PlantationEvaluator
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def ep_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesSimple",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def ep_normandie_criterion(france_map):  # noqa
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées Normandie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesNormandie",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_ep_is_soumis(ep_criteria):  # noqa
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


def test_ep_normandie_interdit(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt10m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139896816121265, "lng": -0.1718410849571228},
            {"lat": 49.13988277820264, "lng": -0.17171770334243774},
        ]
    )
    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt10m_1, hedge_gt20m])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit"


def test_ep_normandie_dispense(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt10m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139896816121265, "lng": -0.1718410849571228},
            {"lat": 49.13988277820264, "lng": -0.17171770334243774},
        ]
    )
    hedge_lt10m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13984943813004, "lng": -0.17185986042022708},
            {"lat": 49.139831890714404, "lng": -0.17174050211906436},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt10m_1, hedge_lt10m_2])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_10m"


def test_ep_normandie_dispense_20m(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt10m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139896816121265, "lng": -0.1718410849571228},
            {"lat": 49.13988277820264, "lng": -0.17171770334243774},
        ]
    )
    hedge_lt10m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13984943813004, "lng": -0.17185986042022708},
            {"lat": 49.139831890714404, "lng": -0.17174050211906436},
        ]
    )
    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ]
    )
    hedge_lt20m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13964588772662, "lng": -0.1719041168689728},
            {"lat": 49.139618689118024, "lng": -0.17169624567031863},
        ]
    )
    hedges = HedgeDataFactory(
        hedges=[hedge_lt10m_1, hedge_lt10m_2, hedge_lt20m_1, hedge_lt20m_2]
    )

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_20m"


def test_ep_normandie_interdit_20m(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt10m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139896816121265, "lng": -0.1718410849571228},
            {"lat": 49.13988277820264, "lng": -0.17171770334243774},
        ]
    )
    hedge_lt10m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13984943813004, "lng": -0.17185986042022708},
            {"lat": 49.139831890714404, "lng": -0.17174050211906436},
        ]
    )
    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ]
    )
    hedge_lt20m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13964588772662, "lng": -0.1719041168689728},
            {"lat": 49.139618689118024, "lng": -0.17169624567031863},
        ]
    )
    hedges = HedgeDataFactory(
        hedges=[hedge_lt10m_1, hedge_lt10m_2, hedge_lt20m_1, hedge_lt20m_2]
    )

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "interdit"


def test_ep_normandie_dispense_coupe_a_blanc(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__mode_destruction="coupe_a_blanc",
    )
    hedge_lt20m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13964588772662, "lng": -0.1719041168689728},
            {"lat": 49.139618689118024, "lng": -0.17169624567031863},
        ],
        additionalData__mode_destruction="coupe_a_blanc",
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1, hedge_lt20m_2])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_coupe_a_blanc"


def test_ep_normandie_interdit_remplacement(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__mode_destruction="coupe_a_blanc",
    )
    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1, hedge_gt20m])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "interdit_remplacement"


def test_ep_normandie_derogation_simplifiee(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__mode_destruction="coupe_a_blanc",
    )
    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1, hedge_gt20m])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "derogation_simplifiee"


def test_min_length_condition_normandie(ep_normandie_criterion):  # noqa
    ConfigHaieFactory()

    hedge_lt10m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139896816121265, "lng": -0.1718410849571228},
            {"lat": 49.13988277820264, "lng": -0.17171770334243774},
        ]
    )
    hedge_lt10m_2 = HedgeFactory(
        latLngs=[
            {"lat": 49.13984943813004, "lng": -0.17185986042022708},
            {"lat": 49.139831890714404, "lng": -0.17174050211906436},
        ]
    )
    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__mode_destruction="coupe_a_blanc",
    )
    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(
        hedges=[hedge_lt10m_1, hedge_lt10m_2, hedge_lt20m_1, hedge_gt20m]
    )
    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "department": "44",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    evaluator = PlantationEvaluator(moulinette, hedges)

    assert evaluator.get_context().get("minimum_length_to_plant") == 69
