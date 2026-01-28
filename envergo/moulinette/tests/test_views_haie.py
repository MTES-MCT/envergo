from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.analytics.models import Event
from envergo.geodata.conftest import (  # noqa
    bizous_town_center,
    france_map,
    loire_atlantique_department,
    loire_atlantique_map,
)
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)

pytestmark = pytest.mark.django_db


HOME_TITLE = "Projet de destruction de haies ou alignements d'arbres"
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)


@pytest.fixture(autouse=False)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    regulation = RegulationFactory(
        regulation="conditionnalite_pac",
        evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8Regulation",
    )
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=loire_atlantique_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_triage(client):
    DCConfigHaieFactory(department_doctrine_html="<h2>Doctrine du département</h2>")

    url = reverse("triage")
    params = "department=44"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "<h2>Doctrine du département</h2>" in content
    assert Event.objects.get(
        category="simulateur", event="localisation", metadata__user_type="anonymous"
    )

    # GIVEN an invalid department code
    params = "department=00"
    full_url = f"{url}?{params}"
    # WHEN visit triage form
    res = client.get(full_url)
    # THEN redirect to homepage
    assert res.status_code == 302
    assert res.url == "/#simulateur"


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_triage_result(client):

    DCConfigHaieFactory(
        department_doctrine_html="<h2>Doctrine du département</h2>",
        hedge_maintenance_html="<h2>kikoo</h2>",
    )

    url = reverse("moulinette_result")
    params = "department=44&element=haie&travaux=entretien"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "Votre projet n'est pas encore pris en compte par le simulateur" in content
    assert "<h2>kikoo</h2>" in content
    assert Event.objects.get(
        category="simulateur", event="soumission_autre", metadata__user_type="anonymous"
    )

    params = "department=44&element=bosquet&travaux=entretien"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "Votre projet n'est pas encore pris en compte par le simulateur" in content
    assert "<h2>kikoo</h2>" not in content

    params = "department=44&element=haie&travaux=destruction"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 302
    assert res["Location"].startswith("/simulateur/formulaire/")

    # GIVEN an invalid department code
    params = "department=00&element=haie&travaux=destruction"
    full_url = f"{url}?{params}"
    # WHEN visit triage form
    res = client.get(full_url)
    # THEN redirect to homepage
    assert res.status_code == 302
    assert res.url == "/#simulateur"


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_moulinette_form_with_invalid_triage(client):

    DCConfigHaieFactory(
        department_doctrine_html="<h2>Doctrine du département</h2>",
        hedge_maintenance_html="<h2>kikoo</h2>",
    )

    url = reverse("moulinette_form")
    params = "department=44&element=haie"  # Missing the "travaux" value
    full_url = f"{url}?{params}"
    res = client.get(full_url, follow=True)

    assert len(res.redirect_chain) == 1
    assert res.redirect_chain[0][0].startswith("/simulateur/triage/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_invalid_department_result(client):
    """Test simulation with querystring not valid department"""

    # GIVEN config haie and haies
    DCConfigHaieFactory()
    haies = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False})]
    )

    # WHEN data has invalid department
    data = {
        "profil": "autre",
        "element": "haie",
        "motif": "amelioration_ecologique",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "travaux": "destruction",
        "haies": str(haies.id),
        "department": "00",
    }
    # THEN result page redirect to home simulator
    url = reverse("moulinette_result")
    params = urlencode(data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)
    assert res.status_code == 302
    assert res.url == "/#simulateur"


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_debug_result(client):
    """WIP: Test for debug page.
    Missing fixtures criteria ep and pac for MoulinetteHaie"""

    DCConfigHaieFactory()
    haies = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False})]
    )

    data = {
        "profil": "autre",
        "element": "haie",
        "motif": "amelioration_ecologique",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "travaux": "destruction",
        "haies": str(haies.id),
        "department": "44",
        "debug": "true",
    }
    url = reverse("moulinette_result")
    params = urlencode(data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    # assertTemplateUsed(res, "haie/moulinette/result_debug.html")


@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
@patch("envergo.hedges.services.get_replantation_coefficient")
def test_result_d_view_with_R_gt_0(mock_R, client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory()
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    mock_R.return_value = 1.0
    res = client.get(f"{url}?{query}")

    assert "Déposer une demande sans plantation" not in res.content.decode()
    assert Event.objects.get(
        category="simulateur", event="soumission_d", metadata__user_type="anonymous"
    )


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
@patch("envergo.hedges.services.get_replantation_coefficient")
def test_result_d_view_with_R_eq_0(mock_R, client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory()
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    mock_R.return_value = 0.0
    res = client.get(f"{url}?{query}")

    # R should be 0
    assert "Déposer une demande sans plantation" in res.content.decode()


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_result_d_view_non_soumis_with_r_gt_0(client):
    DCConfigHaieFactory()
    hedge_lt5m = HedgeFactory(
        latLngs=[
            {"lat": 49.37830760743562, "lng": 0.10241746902465822},
            {"lat": 49.37828490574639, "lng": 0.10244965553283693},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt5m])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 20000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    res = client.get(f"{url}?{query}")

    assert "Déposer une demande sans plantation" not in res.content.decode()


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
@patch("envergo.hedges.services.get_replantation_coefficient")
def test_result_p_view(mock_R, client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory()
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result_plantation")
    query = urlencode(data)
    mock_R.return_value = 0.0
    client.get(f"{url}?{query}")

    assert Event.objects.get(
        category="simulateur", event="soumission_p", metadata__user_type="anonymous"
    )


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_moulinette_post_form_error(client):
    DCConfigHaieFactory()
    url = reverse("moulinette_form")
    data = {
        "foo": "bar",
        "department": "44",
        "element": "haie",
        "travaux": "destruction",
    }
    res = client.post(f"{url}?department=44&element=haie&travaux=destruction", data)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert FORM_ERROR in res.content.decode()
    error_event = Event.objects.get(
        category="erreur", event="formulaire-simu", metadata__user_type="anonymous"
    )
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "haies": [
            {
                "code": "required",
                "message": "Aucune haie n’a été saisie. Cliquez sur le bouton "
                "ci-dessus pour\n"
                "            localiser les haies à détruire.",
            }
        ],
        "localisation_pac": [
            {"code": "required", "message": "Ce champ est obligatoire."}
        ],
        "motif": [{"code": "required", "message": "Ce champ est obligatoire."}],
        "reimplantation": [
            {"code": "required", "message": "Ce champ est obligatoire."}
        ],
    }
    assert "data" in error_event.metadata
    assert error_event.metadata["data"] == data


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_result_p_view_with_hedges_to_remove_outside_department(client):
    """Test if a warning is displayed on result pages when hedges to remove are outside department"""

    # GIVEN a moulinette with at least an hedge to remove outside the department
    DCConfigHaieFactory()
    hedge_14 = HedgeFactory(
        latLngs=[
            {"lat": 49.37830760743562, "lng": 0.10241746902465822},
            {"lat": 49.37828490574639, "lng": 0.10244965553283693},
        ]
    )  # this hedge is in department 14
    hedges = HedgeDataFactory(hedges=[hedge_14])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",  # department 44 is given
        "haies": hedges.id,
        "lineaire_total": 20000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)

    # WHEN requesting the result plantation page
    res = client.get(f"{url}?{query}")

    # THEN the result page is displayed with a warning
    assert res.context["has_hedges_outside_department"]
    assert "Le projet est hors du département sélectionné" in res.content.decode()

    # Given hedges in department 44 and accross the department border
    hedge_44 = HedgeFactory(
        latLngs=[
            {"lat": 47.202984120693635, "lng": -1.7100316286087038},
            {"lat": 47.201198235567496, "lng": -1.7097365856170657},
        ]
    )
    hedge_44_85 = HedgeFactory(
        latLngs=[
            {"lat": 47.05281499678513, "lng": -1.2435150146484377},
            {"lat": 47.103783870991634, "lng": -1.1837768554687502},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_44, hedge_44_85])
    data["haies"] = hedges.id
    query = urlencode(data)

    # WHEN requesting the result plantation page
    res = client.get(f"{url}?{query}")

    # THEN the result page is displayed without warning
    assert not res.context["has_hedges_outside_department"]
    assert "Le projet est hors du département sélectionné" not in res.content.decode()


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_confighaie_settings_view(
    client,
    loire_atlantique_department,  # noqa
    haie_user,
    haie_instructor_44,
    admin_user,
):
    """Test config haie settings view"""
    DCConfigHaieFactory(department=loire_atlantique_department)
    admin_user.departments.add(loire_atlantique_department)
    url = reverse("confighaie_settings", kwargs={"department": "44"})

    # GIVEN an anonymous visitor
    # WHEN they visit department setting page
    response = client.get(url)
    # THEN response is redirection to login page
    content = response.content.decode()
    assert response.status_code == 302

    # GIVEN a connected user with no right to departement
    client.force_login(haie_user)
    # WHEN they visit department setting page
    response = client.get(url)
    # THEN response is 403
    assert response.status_code == 403

    # GIVEN an instructor user
    client.force_login(haie_instructor_44)
    # WHEN they visit department setting page
    response = client.get(url)
    # THEN department config page is displayed
    content = response.content.decode()
    assert response.status_code == 200
    assert "Département : Loire-Atlantique (44)" in content
    # AND instructor emails are visible, not admin ones
    assert haie_user.email not in content
    assert haie_instructor_44.email in content
    assert admin_user.email not in content

    # GIVEN an admin user
    client.force_login(admin_user)
    # WHEN they visit department setting page
    response = client.get(url)
    # THEN department config page is displayed
    content = response.content.decode()
    assert response.status_code == 200
    assert "Département : Loire-Atlantique (44)" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_confighaie_settings_view_map_display(
    client,
    haie_instructor_44,
    loire_atlantique_department,  # noqa: F811
    bizous_town_center,  # noqa: F811
    france_map,  # noqa: F811
):
    """Test maps display in department setting view"""

    DCConfigHaieFactory(department=loire_atlantique_department)
    url = reverse("confighaie_settings", kwargs={"department": "44"})
    bizous_town_center.departments = [loire_atlantique_department.department]
    bizous_town_center.save()

    regulation_code_rural = RegulationFactory(
        regulation="code_rural_haie",
        evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRuralHaieRegulation",
    )
    CriterionFactory(
        title="Code rural L126-3",
        regulation=regulation_code_rural,
        evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRural",
        activation_map=france_map,
        activation_mode="department_centroid",
    )

    n2000_regulation = RegulationFactory(
        regulation="natura2000_haie",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000HaieRegulation",
    )
    n2000_perimeter = PerimeterFactory(
        name="N2000 Bizous",
        activation_map=bizous_town_center,
        regulations=[n2000_regulation],
    )
    CriterionFactory(
        title="Natura 2000 Haie > Haie Bizous",
        regulation=n2000_regulation,
        perimeter=n2000_perimeter,
        evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
        evaluator_settings={"result": "soumis"},
    )

    # GIVEN an instructor user
    client.force_login(haie_instructor_44)
    # WHEN they visit department setting page
    response = client.get(url)
    # THEN department config page is displayed
    content = response.content.decode()

    assert n2000_perimeter.activation_map.name in content


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_result_p_view_with_hedges_to_plant_intersecting_perimeters(
    client, bizous_town_center  # noqa
):

    # GIVEN a moulinette with an hedge to plant inside N2000 perimeters and site proteges perimeter
    sites_proteges_regulation = RegulationFactory(
        regulation="sites_proteges_haie",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesProtegesRegulation",
    )
    n2000_regulation = RegulationFactory(
        regulation="natura2000_haie",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000HaieRegulation",
    )
    spr_perimeter = PerimeterFactory(
        name="MH Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )
    n2000_perimeter = PerimeterFactory(
        name="N2000 Bizous",
        activation_map=bizous_town_center,
        regulations=[n2000_regulation],
    )

    CriterionFactory(
        title="Sites Patrimoniaux Remarquables",
        regulation=sites_proteges_regulation,
        perimeter=spr_perimeter,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )

    CriterionFactory(
        title="Natura 2000 Haie > Haie Bizous",
        regulation=n2000_regulation,
        perimeter=n2000_perimeter,
        evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
        evaluator_settings={"result": "soumis"},
    )
    hedge_inside = HedgeFactory(
        type="TO_PLANT",
        latLngs=[
            {"lat": 43.06930871579473, "lng": 0.4421436860179369},
            {"lat": 43.069162248282396, "lng": 0.44236765047068033},
        ],
    )
    hedge_outside = HedgeFactory(
        type="TO_REMOVE",
        latLngs=[
            {"lat": 43.09248072614743, "lng": 0.48007431760217484},
            {"lat": 43.09280782621999, "lng": 0.48095944654749073},
        ],
    )
    hedges = HedgeDataFactory(hedges=[hedge_inside, hedge_outside])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 20000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)

    # WHEN requesting the result plantation page with droit constant
    config_44 = DCConfigHaieFactory()
    res = client.get(f"{url}?{query}")

    # THEN the result page is displayed with a warning listing all regulations
    assert (
        sites_proteges_regulation
        in res.context["hedges_to_plant_intersecting_regulations_perimeter"]
    )
    assert (
        n2000_regulation
        in res.context["hedges_to_plant_intersecting_regulations_perimeter"]
    )
    assert (
        "La localisation des linéaires à planter dans des zones sensibles "
        in res.content.decode()
    )

    # # Given a department configured as régime unique
    config_44.delete()
    RUConfigHaieFactory()
    # WHEN requesting the result plantation page with droit constant
    res = client.get(f"{url}?{query}")

    # THEN the result page is displayed with a warning listing only regulations that can be in "autorisation"
    assert (
        sites_proteges_regulation
        in res.context["hedges_to_plant_intersecting_regulations_perimeter"]
    )
    assert (
        n2000_regulation
        not in res.context["hedges_to_plant_intersecting_regulations_perimeter"]
    )
    assert (
        "La localisation des linéaires à planter dans des zones sensibles "
        in res.content.decode()
    )
