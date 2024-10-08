import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def evalenv_criteria(france_map):  # noqa
    ConfigAmenagementFactory(
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
    )
    evalenv = RegulationFactory(regulation="eval_env")
    n2000 = RegulationFactory(regulation="natura2000")
    criteria = [
        CriterionFactory(
            title="Evaluation environnementale",
            regulation=evalenv,
            evaluator="envergo.moulinette.regulations.evalenv.Emprise",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="EE",
            regulation=n2000,
            evaluator="envergo.moulinette.regulations.natura2000.EvalEnv",
            activation_map=france_map,
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.4961953,
        "lng": 0.7504093,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
        "emprise": footprint,
        "zone_u": "non",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
    }


@pytest.mark.parametrize("footprint", [40000])
def test_ein_if_evalenv_systematique(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.evaluate()

    assert moulinette.eval_env.emprise.result == "systematique"
    assert moulinette.natura2000.eval_env.result_code == "soumis_systematique"
    assert moulinette.natura2000.eval_env.result == "soumis"
    assert moulinette.natura2000.result == "soumis"


@pytest.mark.parametrize("footprint", [40000])
def test_ein_if_evalenv_cas_par_cas(moulinette_data):
    moulinette_data["zone_u"] = "oui"
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.evaluate()

    assert moulinette.eval_env.emprise.result == "cas_par_cas"
    assert moulinette.natura2000.eval_env.result_code == "soumis_cas_par_cas"
    assert moulinette.natura2000.eval_env.result == "soumis"
    assert moulinette.natura2000.result == "soumis"


@pytest.mark.parametrize("footprint", [5])
def test_no_ein_if_evalenv_non_soumis(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.evaluate()

    assert moulinette.eval_env.emprise.result == "non_soumis"
    assert moulinette.natura2000.eval_env.result_code == "non_soumis"
    assert moulinette.natura2000.eval_env.result == "non_soumis"
    assert moulinette.natura2000.result == "non_soumis"
