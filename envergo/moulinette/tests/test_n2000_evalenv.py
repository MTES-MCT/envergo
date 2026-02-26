import pytest

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import make_amenagement_data


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


def _moulinette(footprint, **extra):
    """Build a moulinette with Mouais coordinates and evalenv fields."""
    defaults = {
        "emprise": footprint,
        "zone_u": "non",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
    }
    defaults.update(extra)
    data = make_amenagement_data(
        created_surface=footprint,
        final_surface=footprint,
        **defaults,
    )
    return MoulinetteAmenagement(data)


def test_ein_if_evalenv_systematique():
    moulinette = _moulinette(40000)

    assert moulinette.eval_env.emprise.result == "systematique"
    assert moulinette.natura2000.eval_env.result_code == "soumis_systematique"
    assert moulinette.natura2000.eval_env.result == "soumis"
    assert moulinette.natura2000.result == "soumis"


def test_ein_if_evalenv_cas_par_cas():
    moulinette = _moulinette(40000, zone_u="oui")

    assert moulinette.eval_env.emprise.result == "cas_par_cas"
    assert moulinette.natura2000.eval_env.result_code == "soumis_cas_par_cas"
    assert moulinette.natura2000.eval_env.result == "soumis"
    assert moulinette.natura2000.result == "soumis"


def test_no_ein_if_evalenv_non_soumis():
    moulinette = _moulinette(5)

    assert moulinette.eval_env.emprise.result == "non_soumis"
    assert moulinette.natura2000.eval_env.result_code == "non_soumis"
    assert moulinette.natura2000.eval_env.result == "non_soumis"
    assert moulinette.natura2000.result == "non_soumis"
