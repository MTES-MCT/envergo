import factory
import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.hedges.services import PlantationEvaluator
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.regulations.ep import get_hedge_compensation_details
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import make_haie_data


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
    return MapFactory(
        name="Zonage Normandie",
        map_type=MAP_TYPES.zonage,
        zones__geometry=MultiPolygon([france_polygon]),
        zones__attributes={"identifiant_zone": "normandie_groupe_1"},
    )


# ---------------------------------------------------------------------------
# EP simple
# ---------------------------------------------------------------------------


def test_ep_is_soumis(ep_criteria):  # noqa
    DCConfigHaieFactory()
    data = make_haie_data(profil="autre")

    for motif_choice in ["amenagement", "autre"]:
        for reimplantation_choice in ["remplacement", "replantation", "non"]:
            data["data"]["motif"] = motif_choice
            data["data"]["reimplantation"] = reimplantation_choice
            moulinette = MoulinetteHaie(data)
            assert moulinette.is_valid(), moulinette.form_errors()
            assert moulinette.result == "soumis", (
                motif_choice,
                reimplantation_choice,
            )


# ---------------------------------------------------------------------------
# EP Normandie
# ---------------------------------------------------------------------------


def test_ep_normandie_interdit(ep_normandie_criterion, zonage_normandie):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="non",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.result == "interdit"


def test_ep_normandie_dispense_10m(ep_normandie_criterion, zonage_normandie):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="non",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == "dispense_10m"


def test_ep_normandie_dispense_20m(ep_normandie_criterion, zonage_normandie):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == "dispense_20m"


def test_ep_normandie_interdit_20m(ep_normandie_criterion, zonage_normandie):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="non",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == "interdit"


def test_ep_normandie_dispense_coupe_a_blanc(
    ep_normandie_criterion, zonage_normandie
):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif="amelioration_culture",
        reimplantation="remplacement",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == "dispense_coupe_a_blanc"


def test_ep_normandie_interdit_remplacement(
    ep_normandie_criterion, zonage_normandie
):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif="amelioration_culture",
        reimplantation="remplacement",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    # Replacing hedges is no longer forbidden in Normandie
    assert moulinette.ep.ep_normandie.result_code == "derogation_simplifiee"


def test_ep_normandie_derogation_simplifiee(
    ep_normandie_criterion, zonage_normandie
):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
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
    DCConfigHaieFactory()

    hedge_gt20m = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_gt20m])
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == "dispense"


# ---------------------------------------------------------------------------
# EP Normandie — L350-3 alignment trees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "motif_result",
    [
        ("amelioration_culture", "a_verifier_L350"),
        ("chemin_acces", "a_verifier_L350"),
        ("securite", "dispense_L350"),
        ("amenagement", "a_verifier_L350"),
        ("amelioration_ecologique", "a_verifier_L350"),
        ("embellissement", "a_verifier_L350"),
        ("autre", "a_verifier_L350"),
    ],
)
def test_ep_normandie_l350(motif_result, ep_normandie_criterion, france_map):  # noqa
    motif, result_code = motif_result
    regulation = RegulationFactory(regulation="alignement_arbres", weight=0)
    CriterionFactory(
        title="Alignement arbres > L350-3",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
        activation_map=france_map,
        activation_mode="department_centroid",
    ),
    DCConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__type_haie="alignement",
        additionalData__bord_voie=True,
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1])
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif=motif,
        reimplantation="replantation",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.ep.ep_normandie.result_code == result_code


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
    DCConfigHaieFactory()

    hedge_lt20m_1 = HedgeFactory(
        latLngs=[
            {"lat": 49.139679227936156, "lng": -0.17190009355545047},
            {"lat": 49.13965115197173, "lng": -0.17171099781990054},
        ],
        additionalData__type_haie="alignement",
        additionalData__bord_voie=True,
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt20m_1])
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif="securite",
        reimplantation="replantation",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    with pytest.raises(RuntimeError) as exc_info:
        MoulinetteHaie(data)

    assert "Criterion must be evaluated before accessing the result code" in str(
        exc_info.value
    )


# ---------------------------------------------------------------------------
# EP Normandie — plantation evaluator
# ---------------------------------------------------------------------------


def test_min_length_condition_normandie(
    ep_normandie_criterion, zonage_normandie
):  # noqa
    DCConfigHaieFactory()

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
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif="amelioration_culture",
        reimplantation="remplacement",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
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
    DCConfigHaieFactory()
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
    hedges = HedgeDataFactory(hedges=[hedge_gt20m])
    data = make_haie_data(
        hedges=hedges,
        profil="autre",
        motif="amelioration_culture",
        reimplantation="remplacement",
        localisation_pac="oui",
        numero_pacage="012345678",
    )

    moulinette = MoulinetteHaie(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    evaluator = PlantationEvaluator(moulinette, hedges)

    assert evaluator.replantation_coefficient == r


# ---------------------------------------------------------------------------
# Hedge compensation details (unit test, no DB)
# ---------------------------------------------------------------------------


def test_get_hedge_compensation_details():
    hedge_neb_rc_aa_cap = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ],
        additionalData=factory.Dict(
            {
                "mode_destruction": "coupe_a_blanc",
                "type_haie": "alignement",
                "bord_voie": True,
                "essences_non_bocageres": True,
                "recemment_plantee": True,
                "proximite_point_eau": False,
                "connexion_boisement": False,
            }
        ),
    )

    details = get_hedge_compensation_details(hedge_neb_rc_aa_cap, 1.0)

    assert (
        details["properties"]
        == "essences non bocagères, récemment plantée, coupe à blanc, L350-3"
    )

    hedge_aa_cap = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ],
        additionalData=factory.Dict(
            {
                "mode_destruction": "coupe_a_blanc",
                "type_haie": "alignement",
                "bord_voie": True,
                "essences_non_bocageres": False,
                "recemment_plantee": False,
                "proximite_point_eau": False,
                "connexion_boisement": False,
            }
        ),
    )

    details = get_hedge_compensation_details(hedge_aa_cap, 1.0)

    assert details["properties"] == "coupe à blanc, L350-3"

    hedge_nothing = HedgeFactory(
        latLngs=[
            {"lat": 49.1395362158265, "lng": -0.17191082239151004},
            {"lat": 49.1394993660136, "lng": -0.17153665423393252},
        ],
        additionalData=factory.Dict(
            {
                "mode_destruction": "autre",
                "type_haie": "alignement",
                "bord_voie": False,
                "essences_non_bocageres": False,
                "recemment_plantee": False,
                "proximite_point_eau": False,
                "connexion_boisement": False,
            }
        ),
    )

    details = get_hedge_compensation_details(hedge_nothing, 1.0)

    assert details["properties"] == "-"
