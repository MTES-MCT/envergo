import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.geodata.conftest import france_map  # noqa
from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
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


@pytest.fixture
def zonage_normandie(france_map):  # noqa
    zonage_normandie = MapFactory(
        name="Zonage Normandie",
        map_type=MAP_TYPES.zonage,
        zones__geometry=MultiPolygon([france_polygon]),
        zones__attributes={"identifiant_zone": "normandie_groupe_1"},
    )
    return zonage_normandie


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


def test_ep_normandie_interdit(ep_normandie_criterion, zonage_normandie):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit"


def test_ep_normandie_dispense_10m(ep_normandie_criterion, zonage_normandie):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_10m"


def test_ep_normandie_dispense_20m(ep_normandie_criterion, zonage_normandie):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_20m"


def test_ep_normandie_interdit_20m(ep_normandie_criterion, zonage_normandie):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "interdit"


def test_ep_normandie_dispense_coupe_a_blanc(
    ep_normandie_criterion, zonage_normandie
):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_coupe_a_blanc"


def test_ep_normandie_interdit_remplacement(
    ep_normandie_criterion, zonage_normandie
):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "interdit_remplacement"


def test_ep_normandie_derogation_simplifiee(
    ep_normandie_criterion, zonage_normandie
):  # noqa
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
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "derogation_simplifiee"


def test_ep_normandie_dispense(ep_normandie_criterion):  # noqa
    MapFactory(
        name="Zonage Normandie",
        map_type=MAP_TYPES.zonage,
        zones=[
            ZoneFactory(
                geometry=MultiPolygon([france_polygon]),
                attributes={"identifiant_zone": "normandie_groupe_5"},
            )
        ],
    )
    ConfigHaieFactory()

    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_gt20m])

    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "department": "44",
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense"


def test_ep_normandie_dispense_l350(ep_normandie_criterion, france_map):  # noqa
    regulation = RegulationFactory(regulation="alignement_arbres", weight=0)
    CriterionFactory(
        title="Alignement arbres > L350-3",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
        activation_map=france_map,
        activation_mode="department_centroid",
    ),
    ConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__type_haie="alignement",
        additionalData__bord_voie=True,
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1])

    data = {
        "profil": "autre",
        "motif": "securite",
        "reimplantation": "replantation",
        "department": "44",
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.ep.ep_normandie.result_code == "dispense_L350"


def test_ep_normandie_without_alignement_arbre_evaluation_should_raise(
    ep_normandie_criterion, france_map  # noqa
):
    regulation = RegulationFactory(regulation="alignement_arbres", weight=3)
    CriterionFactory(
        title="Alignement arbres > L350-3",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
        activation_map=france_map,
        activation_mode="department_centroid",
    ),
    ConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__type_haie="alignement",
        additionalData__bord_voie=True,
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1])

    data = {
        "profil": "autre",
        "motif": "securite",
        "reimplantation": "replantation",
        "department": "44",
        "numero_pacage": "012345678",
        "haies": hedges,
    }

    with pytest.raises(RuntimeError) as exc_info:
        MoulinetteHaie(data, data, False)

    assert "Criterion must be evaluated before accessing the result code" in str(
        exc_info.value
    )


def test_min_length_condition_normandie(
    ep_normandie_criterion, zonage_normandie
):  # noqa
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

    assert evaluator.get_context().get("minimum_length_to_plant") == 59


@pytest.mark.parametrize(
    "params",
    [
        ("degradee", 1.6),
        ("buissonnante", 1.8),
        ("arbustive", 2),
        ("alignement", 2),
        ("mixte", 2.2),
    ],
)
def test_replantation_coefficient_normandie(
    ep_normandie_criterion, params: tuple[str, float]
):  # noqa
    ConfigHaieFactory()
    hedge_type, r = params
    MapFactory(
        name="Zonage Normandie",
        map_type=MAP_TYPES.zonage,
        zones__geometry=MultiPolygon([france_polygon]),
        zones__attributes={"identifiant_zone": "normandie_groupe_1"},
    )

    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ],
        additionalData__type_haie=hedge_type,
    )
    hedges = HedgeDataFactory(
        hedges=[hedge_gt20m],
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

    assert evaluator.replantation_coefficient == r
