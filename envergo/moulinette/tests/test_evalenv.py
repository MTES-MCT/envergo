import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

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


@pytest.fixture
def moulinette_data(footprint):
    data = {
        # Bizou coordinates
        "lat": 48.496195,
        "lng": 0.750409,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
        "emprise": 20000,
        "zone_u": "oui",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
        "operation_amenagement": "non",
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize("footprint", [9500])
def test_evalenv_small_footprint(moulinette_data):
    del moulinette_data["data"]["zone_u"]
    del moulinette_data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [10500])
def test_evalenv_medium(moulinette_data):
    del moulinette_data["data"]["zone_u"]
    del moulinette_data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data["data"]["emprise"] = 42
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [40500])
def test_evalenv_wide_footprint(moulinette_data):
    moulinette_data["data"]["emprise"] = 42
    del moulinette_data["data"]["zone_u"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data["data"]["zone_u"] = "oui"
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.has_missing_data()


@pytest.mark.parametrize("footprint", [9500])
def test_evalenv_emprise_non_soumis(moulinette_data):
    del moulinette_data["data"]["zone_u"]
    del moulinette_data["data"]["emprise"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.emprise.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_emprise_non_soumis_2(moulinette_data):
    del moulinette_data["data"]["emprise"]
    moulinette_data["data"]["emprise"] = 5000

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.emprise.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_emprise_cas_par_cas(moulinette_data):
    del moulinette_data["data"]["zone_u"]
    moulinette_data["data"]["emprise"] = 10000

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [40000])
def test_evalenv_zone_u_cas_par_cas(moulinette_data):
    moulinette_data["data"]["emprise"] = 40000
    moulinette_data["data"]["zone_u"] = "oui"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.emprise.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [40000])
def test_evalenv_zone_u_systematique(moulinette_data):
    moulinette_data["data"]["emprise"] = 40000
    moulinette_data["data"]["zone_u"] = "non"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.emprise.result == "systematique"


@pytest.mark.parametrize("footprint", [2000])
def test_evalenv_surface_plancher_non_soumis(moulinette_data):
    del moulinette_data["data"]["surface_plancher_sup_thld"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


@pytest.mark.parametrize("footprint", [3000])
def test_evalenv_surface_plancher_non_soumis_2(moulinette_data):
    del moulinette_data["data"]["surface_plancher_sup_thld"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data["data"]["surface_plancher_sup_thld"] = "non"
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.surface_plancher.result == "non_soumis"


@pytest.mark.parametrize("footprint", [3000])
def test_evalenv_surface_plancher_cas_par_cas(moulinette_data):
    moulinette_data["data"]["surface_plancher_sup_thld"] = "oui"
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.surface_plancher.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [5000])
def test_evalenv_terrain_assiette_non_soumis(moulinette_data):
    del moulinette_data["data"]["terrain_assiette"]
    del moulinette_data["data"]["operation_amenagement"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.has_missing_data()
    assert moulinette.eval_env.terrain_assiette.result == "non_concerne"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_non_concerne(moulinette_data):
    del moulinette_data["data"]["terrain_assiette"]
    del moulinette_data["data"]["operation_amenagement"]

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.has_missing_data()

    moulinette_data["data"]["terrain_assiette"] = 150000
    moulinette_data["data"]["operation_amenagement"] = "non"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.terrain_assiette.result == "non_concerne"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_non_soumis_2(moulinette_data):
    moulinette_data["data"]["terrain_assiette"] = 45000
    moulinette_data["data"]["operation_amenagement"] = "oui"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.terrain_assiette.result == "non_soumis"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_cas_par_cas(moulinette_data):
    moulinette_data["data"]["terrain_assiette"] = 95000
    moulinette_data["data"]["operation_amenagement"] = "oui"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.terrain_assiette.result == "cas_par_cas"


@pytest.mark.parametrize("footprint", [10000])
def test_evalenv_terrain_assiette_systematique(moulinette_data):
    moulinette_data["data"]["terrain_assiette"] = 150000
    moulinette_data["data"]["operation_amenagement"] = "oui"

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.eval_env.terrain_assiette.result == "systematique"


def test_evalenv_non_soumis_no_optional_criteria(admin_client):
    """When no optional form is activated, we can show the result."""

    ConfigAmenagementFactory()

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"

    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet n’est pas soumis à évaluation environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        in res.content.decode()
    )
    assert (
        "Le projet n’est pas soumis à évaluation environnementale, ni à examen au cas par cas."
        not in res.content.decode()
    )


def test_evalenv_non_soumis_missing_optional_criteria(admin_client):
    """When optional data is missing, we don't show the result page."""

    ConfigAmenagementFactory()

    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=0_49"
    )
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

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
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet n’est pas soumis à évaluation environnementale au titre des seuils "
        "de surface plancher, d'emprise au sol et de terrain d'assiette."
        not in res.content.decode()
    )
    assert (
        "Le projet n’est pas soumis à évaluation environnementale, ni à examen au cas par cas."
        in res.content.decode()
    )


def test_evalenv_rubrique44(admin_client):
    ConfigAmenagementFactory()

    # Type d'equipement concerné et capacité d'accueil >= 1000 => Cas par cas
    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=sport"
        "&evalenv_rubrique_44-capacite_accueil=gte_1000"
    )
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet mène à l’existence d’un équipement sportif, de loisirs, ou lié à une activité culturelle, d’une "
        "capacité d’accueil de plus de 1000 personnes" in res.content.decode()
    )

    # Type d'equipement concerné et capacité d'accueil < 1000 => non soumis
    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=sport"
        "&evalenv_rubrique_44-capacite_accueil=lt_1000"
    )
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet porte sur un équipement sportif, de loisirs, ou lié à une activité culturelle, mais dont la capacité"
        " d’accueil est inférieure à 1000 personnes" in res.content.decode()
    )

    # Type d'equipement non concerné => non soumis
    url = reverse("moulinette_result")
    params = (
        "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
        "&evalenv_rubrique_44-activate=on&evalenv_rubrique_44-type=autre"
        "&evalenv_rubrique_44-capacite_accueil=lt_1000"
    )
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    assert (
        "Le projet ne concerne pas un équipement sportif, de loisirs, ou d’activités culturelles."
        in res.content.decode()
    )


@pytest.mark.parametrize("footprint", [40000])
def test_evalenv_subtractive_actions_to_take(moulinette_data):
    ConfigAmenagementFactory()
    moulinette_data["data"]["terrain_assiette"] = 150000
    moulinette_data["data"]["operation_amenagement"] = "oui"

    # Mouais coordinates in 44
    moulinette_data["data"]["lat"] = 47.696706
    moulinette_data["data"]["lng"] = -1.646947

    moulinette = MoulinetteAmenagement(moulinette_data)
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
