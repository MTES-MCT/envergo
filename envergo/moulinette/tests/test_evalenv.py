import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ActionToTakeFactory,
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import COORDS_BIZOU, make_amenagement_data


def _bizou_data(created_surface, **extra):
    """Shortcut for Bizou-located amenagement data with common evalenv fields."""
    defaults = {
        "emprise": 20000,
        "zone_u": "oui",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
        "operation_amenagement": "non",
    }
    defaults.update(extra)
    return make_amenagement_data(
        lat=COORDS_BIZOU[0], lng=COORDS_BIZOU[1],
        created_surface=created_surface, final_surface=created_surface,
        **defaults,
    )


@pytest.fixture(autouse=True)
def evalenv_criteria(france_map):  # noqa
    regulation = RegulationFactory(
        regulation="eval_env",
        evaluator="envergo.moulinette.regulations.evalenv.EvalEnvRegulation",
    )
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
        CriterionFactory(
            title="Equipement sportif",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.EquipementSportif",
            activation_map=france_map,
            is_optional=True,
        ),
    ]
    return criteria


# ---------------------------------------------------------------------------
# Missing data detection
# ---------------------------------------------------------------------------


def test_evalenv_small_footprint():
    data = _bizou_data(9500)
    del data["data"]["zone_u"]
    del data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert not moulinette.has_missing_data()


def test_evalenv_medium():
    data = _bizou_data(10500)
    del data["data"]["zone_u"]
    del data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.has_missing_data()

    data["data"]["emprise"] = 42
    moulinette = MoulinetteAmenagement(data)
    assert not moulinette.has_missing_data()


def test_evalenv_wide_footprint():
    data = _bizou_data(40500, emprise=42)
    del data["data"]["zone_u"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.has_missing_data()

    data["data"]["zone_u"] = "oui"
    moulinette = MoulinetteAmenagement(data)
    assert not moulinette.has_missing_data()


# ---------------------------------------------------------------------------
# Emprise
# ---------------------------------------------------------------------------


def test_evalenv_emprise_non_soumis():
    data = _bizou_data(9500)
    del data["data"]["zone_u"]
    del data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.emprise.result == "non_soumis"


def test_evalenv_emprise_non_soumis_2():
    data = _bizou_data(10000, emprise=5000)
    del data["data"]["emprise"]
    data["data"]["emprise"] = 5000

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.emprise.result == "non_soumis"


def test_evalenv_emprise_cas_par_cas():
    data = _bizou_data(10000, emprise=10000)
    del data["data"]["zone_u"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


def test_evalenv_zone_u_cas_par_cas():
    data = _bizou_data(40000, emprise=40000, zone_u="oui")

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


def test_evalenv_zone_u_systematique():
    data = _bizou_data(40000, emprise=40000, zone_u="non")

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.emprise.result == "systematique"


# ---------------------------------------------------------------------------
# Surface plancher
# ---------------------------------------------------------------------------


def test_evalenv_surface_plancher_non_soumis():
    data = _bizou_data(2000)
    del data["data"]["surface_plancher_sup_thld"]

    moulinette = MoulinetteAmenagement(data)
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


def test_evalenv_surface_plancher_non_soumis_2():
    data = _bizou_data(3000)
    del data["data"]["surface_plancher_sup_thld"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.has_missing_data()

    data["data"]["surface_plancher_sup_thld"] = "non"
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


def test_evalenv_surface_plancher_cas_par_cas():
    data = _bizou_data(3000, surface_plancher_sup_thld="oui")
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.surface_plancher.result == "cas_par_cas"


# ---------------------------------------------------------------------------
# Terrain d'assiette
# ---------------------------------------------------------------------------


def test_evalenv_terrain_assiette_non_soumis():
    data = _bizou_data(5000)
    del data["data"]["terrain_assiette"]
    del data["data"]["operation_amenagement"]

    moulinette = MoulinetteAmenagement(data)
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.terrain_assiette.result == "non_concerne"


def test_evalenv_terrain_assiette_non_concerne():
    data = _bizou_data(10000)
    del data["data"]["terrain_assiette"]
    del data["data"]["operation_amenagement"]

    moulinette = MoulinetteAmenagement(data)
    assert moulinette.has_missing_data()

    data["data"]["terrain_assiette"] = 150000
    data["data"]["operation_amenagement"] = "non"
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.terrain_assiette.result == "non_concerne"


def test_evalenv_terrain_assiette_non_soumis_2():
    data = _bizou_data(10000, terrain_assiette=45000, operation_amenagement="oui")
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.terrain_assiette.result == "non_soumis"


def test_evalenv_terrain_assiette_cas_par_cas():
    data = _bizou_data(10000, terrain_assiette=95000, operation_amenagement="oui")
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.terrain_assiette.result == "cas_par_cas"


def test_evalenv_terrain_assiette_systematique():
    data = _bizou_data(10000, terrain_assiette=150000, operation_amenagement="oui")
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.terrain_assiette.result == "systematique"


# ---------------------------------------------------------------------------
# View-level tests — optional criteria rendering
# ---------------------------------------------------------------------------


def test_evalenv_non_soumis_no_optional_criteria(admin_client):
    """When no optional form is activated, we can show the result."""
    ConfigAmenagementFactory()

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    res = admin_client.get(f"{url}?{params}")

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    content = res.content.decode()
    assert (
        "Le projet n’est pas soumis à évaluation environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        in content
    )
    assert (
        "Le projet n’est pas soumis à évaluation environnementale, ni à examen au cas par cas."
        not in content
    )


def test_evalenv_non_soumis_missing_optional_criteria(admin_client):
    """When optional data is missing, we don't show the result page."""
    ConfigAmenagementFactory()

    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=0_49"
    )
    res = admin_client.get(f"{url}?{params}")

    assert res.status_code == 302
    assert res["Location"].startswith("/simulateur/formulaire/")


def test_evalenv_non_soumis_optional_criteria(admin_client):
    ConfigAmenagementFactory()

    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=0_49"
        "&evalenv_rubrique_41-type_stationnement=public"
    )
    res = admin_client.get(f"{url}?{params}")

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    content = res.content.decode()
    assert (
        "Le projet n’est pas soumis à évaluation environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        not in content
    )
    assert (
        "Le projet n’est pas soumis à évaluation environnementale, ni à examen au cas par cas."
        in content
    )


def test_evalenv_rubrique44(admin_client):
    ConfigAmenagementFactory()

    url = reverse("moulinette_result")

    # Type d'equipement concerné et capacité d'accueil >= 1000 => Cas par cas
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=sport"
        "&evalenv_rubrique_44-capacite_accueil=gte_1000"
    )
    res = admin_client.get(f"{url}?{params}")
    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert (
        "Le projet mène à l’existence d’un équipement sportif, de loisirs, ou lié à une activité culturelle, d’une "
        "capacité d’accueil de plus de 1000 personnes" in res.content.decode()
    )

    # Type d'equipement concerné et capacité d'accueil < 1000 => non soumis
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=sport"
        "&evalenv_rubrique_44-capacite_accueil=lt_1000"
    )
    res = admin_client.get(f"{url}?{params}")
    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert (
        "Le projet porte sur un équipement sportif, de loisirs, ou lié à une activité culturelle, mais dont la capacité"
        " d’accueil est inférieure à 1000 personnes" in res.content.decode()
    )

    # Type d'equipement non concerné => non soumis
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=autre"
        "&evalenv_rubrique_44-capacite_accueil=lt_1000"
    )
    res = admin_client.get(f"{url}?{params}")
    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert (
        "Le projet ne concerne pas un équipement sportif, de loisirs, ou d’activités culturelles."
        in res.content.decode()
    )


def test_evalenv_subtractive_actions_to_take():
    ConfigAmenagementFactory()
    ActionToTakeFactory(slug="depot_etude_impact", target="petitioner")
    ActionToTakeFactory(slug="pc_ein", target="instructor")
    data = make_amenagement_data(
        created_surface=40000,
        final_surface=40000,
        emprise=20000,
        zone_u="oui",
        surface_plancher_sup_thld="oui",
        is_lotissement="non",
        terrain_assiette=150000,
        operation_amenagement="oui",
    )
    moulinette = MoulinetteAmenagement(data)
    assert moulinette.eval_env.terrain_assiette.result == "systematique"
    assert moulinette.eval_env.actions_to_take == {
        "to_add": {"depot_etude_impact", "pc_etude_impact"},
        "to_subtract": {"pc_ein"},
    }
    actions_to_take_flatten = {
        target: [action.slug for action in actions_list]
        for target, actions_list in moulinette.actions_to_take.items()
    }
    assert actions_to_take_flatten == {
        "petitioner": ["depot_etude_impact"]
    }  # there is no pc_etude_impact in DB
