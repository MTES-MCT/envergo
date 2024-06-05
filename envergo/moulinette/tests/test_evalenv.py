import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Moulinette
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def evalenv_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="eval_env")
    criteria = [
        CriterionFactory(
            title="Emprise",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.Emprise",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Surface Plancher",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.SurfacePlancher",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Terrain d'assiette",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.TerrainAssiette",
            activation_map=france_map,
        ),
        CriterionFactory(
            title="Aire de stationnement",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.AireDeStationnement",
            activation_map=france_map,
            is_optional=True,
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
        "emprise": 20000,
        "zone_u": "oui",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
    }


@pytest.mark.parametrize("footprint", [9500])
def test_evalenv_small_footprint(moulinette_data):
    del moulinette_data["zone_u"]
    del moulinette_data["emprise"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [10500])
def test_evalenv_medium(moulinette_data):
    del moulinette_data["zone_u"]
    del moulinette_data["emprise"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.has_missing_data()

    moulinette_data["emprise"] = 42
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [40500])
def test_evalenv_wide_footprint(moulinette_data):
    moulinette_data["emprise"] = 42
    del moulinette_data["zone_u"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.has_missing_data()

    moulinette_data["zone_u"] = "oui"
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [9500])
def test_evalenv_emprise_non_soumis(moulinette_data):
    del moulinette_data["zone_u"]
    del moulinette_data["emprise"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.emprise.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_emprise_non_soumis_2(moulinette_data):
    del moulinette_data["emprise"]
    moulinette_data["emprise"] = 5000

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.emprise.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_emprise_cas_par_cas(moulinette_data):
    del moulinette_data["zone_u"]
    moulinette_data["emprise"] = 10000

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [40000])
def test_evalenv_zone_u_cas_par_cas(moulinette_data):
    moulinette_data["emprise"] = 40000
    moulinette_data["zone_u"] = "oui"

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [40000])
def test_evalenv_zone_u_systematique(moulinette_data):
    moulinette_data["emprise"] = 40000
    moulinette_data["zone_u"] = "non"

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.emprise.result == "systematique"


@pytest.mark.parametrize("footprint", [2000])
def test_evalenv_surface_plancher_non_soumis(moulinette_data):
    del moulinette_data["surface_plancher_sup_thld"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


@pytest.mark.parametrize("footprint", [3000])
def test_evalenv_surface_plancher_non_soumis_2(moulinette_data):
    del moulinette_data["surface_plancher_sup_thld"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.has_missing_data()

    moulinette_data["surface_plancher_sup_thld"] = "non"
    moulinette.evaluate()
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


@pytest.mark.parametrize("footprint", [3000])
def test_evalenv_surface_plancher_cas_par_cas(moulinette_data):
    moulinette_data["surface_plancher_sup_thld"] = "oui"
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.surface_plancher.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [5000])
def test_evalenv_terrain_assiette_non_soumis(moulinette_data):
    del moulinette_data["terrain_assiette"]

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.terrain_assiette.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_non_soumis_2(moulinette_data):
    moulinette_data["terrain_assiette"] = 45000

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.terrain_assiette.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_cas_par_cas(moulinette_data):
    moulinette_data["terrain_assiette"] = 95000

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.terrain_assiette.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_systematique(moulinette_data):
    moulinette_data["terrain_assiette"] = 150000

    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.evaluate()
    assert moulinette.eval_env.terrain_assiette.result == "systematique"


def test_evalenv_non_soumis_no_optional_criteria(admin_client):
    MoulinetteConfigFactory()

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"

    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet n’est pas soumis à Évaluation Environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        in res.content.decode()
    )
    assert (
        "Le projet n’est pas soumis à Évaluation Environnementale, ni à examen au cas par cas."
        not in res.content.decode()
    )


def test_evalenv_non_soumis_optional_criteria(admin_client):
    MoulinetteConfigFactory()

    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=0_49"
        "&evalenv_rubrique_41-has_public_emplacement=public"
    )
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet n’est pas soumis à Évaluation Environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        not in res.content.decode()
    )
    assert (
        "Le projet n’est pas soumis à Évaluation Environnementale, ni à examen au cas par cas."
        in res.content.decode()
    )
