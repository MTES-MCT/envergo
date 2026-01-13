from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.geodata.tests.factories import ZoneFactory
from envergo.moulinette.forms import MoulinetteFormAmenagement
from envergo.moulinette.models import ConfigHaie, MoulinetteAmenagement, MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)
from envergo.moulinette.utils import (
    get_moulinette_class_from_site,
    get_moulinette_class_from_url,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def moulinette_config(france_map):  # noqa
    regulation = RegulationFactory()
    PerimeterFactory(
        regulations=[regulation],
        activation_map=france_map,
    )
    classes = [
        "envergo.moulinette.regulations.loisurleau.ZoneHumide",
        "envergo.moulinette.regulations.loisurleau.ZoneInondable",
        "envergo.moulinette.regulations.loisurleau.Ruissellement",
    ]
    for path in classes:
        CriterionFactory(
            regulation=regulation, activation_map=france_map, evaluator=path
        )


@pytest.fixture
def moulinette_data(footprint):
    data = {
        # Mouais coordinates
        "lat": 47.696706,
        "lng": -1.646947,
        "created_surface": 0,
        "final_surface": footprint,
    }
    return {"initial": data, "data": data}


@pytest.fixture
def mouais_church_data(footprint):
    data = {
        "lat": 47.696706,
        "lng": -1.646947,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
    }
    return {"initial": data, "data": data}


def no_zones(_coords):
    return []


def create_zones():
    return [ZoneFactory()]


@pytest.mark.parametrize("footprint", [50])
def test_result_without_contact_data(moulinette_data):
    """When dept. contact info is not set, we cannot run the eval."""

    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.is_evaluation_available()


@pytest.mark.parametrize("footprint", [50])
def test_moulinette_config(moulinette_data):
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert not moulinette.has_config()

    ConfigAmenagementFactory(is_activated=False)
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
    assert moulinette.has_config()


@pytest.mark.parametrize("footprint", [50])
def test_result_with_inactive_contact_data(moulinette_data):
    """Dept contact info is not activated, we cannot run the eval."""

    ConfigAmenagementFactory(is_activated=False)
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.is_valid()
    assert not moulinette.is_evaluation_available()


@pytest.mark.parametrize("footprint", [50])
def test_result_with_contact_data(moulinette_data):
    """Dept contact info is set, we can run the eval."""

    ConfigAmenagementFactory(is_activated=True)
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.is_valid()


@pytest.mark.parametrize("footprint", [50])
def test_moulinette_amenagement_has_specific_behavior(moulinette_data):
    site = SiteFactory()
    ConfigAmenagementFactory(is_activated=True)
    MoulinetteClass = get_moulinette_class_from_site(site)
    moulinette = MoulinetteClass(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.get_main_form_class() == MoulinetteFormAmenagement
    assert moulinette.get_form_template() == "amenagement/moulinette/form.html"
    assert moulinette.get_result_template() == "amenagement/moulinette/result.html"

    MoulinetteClass = get_moulinette_class_from_url("envergo.beta.gouv.fr")
    assert MoulinetteClass is MoulinetteAmenagement


def test_moulinette_haie_has_specific_behavior():
    DCConfigHaieFactory()
    site = SiteFactory()
    site.domain = "haie.beta.gouv.fr"
    MoulinetteClass = get_moulinette_class_from_site(site)
    assert MoulinetteClass is MoulinetteHaie

    MoulinetteClass = get_moulinette_class_from_url("haie.beta.gouv.fr")
    assert MoulinetteClass is MoulinetteHaie


def test_config_haie_has_missing_demarche_simplifiee_number(
    loire_atlantique_department,  # noqa
):
    config_haie = ConfigHaie(department=loire_atlantique_department, is_activated=True)
    with pytest.raises(ValidationError):
        config_haie.validate_constraints()


def test_config_haie_has_invalid_demarche_simplifiee_config(
    loire_atlantique_department,  # noqa
):
    with pytest.raises(ValidationError) as exc_info:
        config_haie = ConfigHaie(
            department=loire_atlantique_department,
            is_activated=True,
            demarche_simplifiee_number="123456789",
            demarche_simplifiee_pre_fill_config={"foo": "bar"},
        )
        config_haie.clean()
    assert exc_info.value.messages == [
        "Cette configuration doit être une liste de champs (ou d'annotations privées) à pré-remplir"
    ]

    with pytest.raises(ValidationError) as exc_info:
        config_haie = ConfigHaie(
            department=loire_atlantique_department,
            is_activated=True,
            demarche_simplifiee_number="123456789",
            demarche_simplifiee_pre_fill_config=[{"foo": "bar"}],
        )
        config_haie.clean()
    assert exc_info.value.messages == [
        "Chaque champ (ou annotation privée) doit contenir au moins l'id côté Démarches Simplifiées et la "
        "source de la valeur côté guichet unique de la haie."
    ]

    with pytest.raises(ValidationError) as exc_info:
        config_haie = ConfigHaie(
            department=loire_atlantique_department,
            is_activated=True,
            demarche_simplifiee_number="123456789",
            demarche_simplifiee_pre_fill_config=[{"id": "123456789", "value": "bar"}],
        )
        config_haie.clean()
    assert exc_info.value.messages == [
        "La source de la valeur bar n'est pas valide pour le champ dont l'id est 123456789"
    ]

    with pytest.raises(
        ValidationError,
        match="Le mapping du champ dont l'id est 123456789 doit être un dictionnaire.",
    ):
        config_haie = ConfigHaie(
            department=loire_atlantique_department,
            is_activated=True,
            demarche_simplifiee_number="123456789",
            demarche_simplifiee_pre_fill_config=[
                {"id": "123456789", "value": "localisation_pac", "mapping": "bar"}
            ],
        )
        config_haie.clean()

    config_haie = ConfigHaie(
        department=loire_atlantique_department,
        is_activated=True,
        demarche_simplifiee_number="123456789",
        demarche_simplifiee_pre_fill_config=[
            {"id": "123456789", "value": "localisation_pac", "mapping": {"foo": "bar"}}
        ],
    )
    config_haie.clean()


def test_regulation_with_map_factory_can_create_a_location_centric_map(
    france_map,  # noqa
):
    regulation = RegulationFactory(
        has_perimeters=True,
        show_map=True,
        map_factory_name="envergo.moulinette.regulations.PerimetersBoundedWithCenterMapMarkerMapFactory",
    )
    regulation.moulinette = MagicMock(
        get_map_center=MagicMock(return_value=(47.0, -1.0))
    )
    PerimeterFactory(
        regulations=[regulation],
        activation_map=france_map,
    )
    PerimeterFactory(
        regulations=[regulation],
        activation_map=france_map,
    )
    assert regulation.map
    assert len(regulation.map.entries) == 2
    assert regulation.map.entries[0].color == regulation.polygon_color
    assert regulation.map.center == regulation.moulinette.get_map_center()
    assert regulation.map.display_marker_at_center


def test_regulation_with_map_factory_can_create_a_hedge_to_remove_map(
    france_map,  # noqa
):
    regulation = RegulationFactory(
        has_perimeters=True,
        show_map=True,
        map_factory_name="envergo.moulinette.regulations.HedgesToRemoveCentricMapFactory",
    )
    regulation.moulinette = MagicMock(
        get_map_center=MagicMock(return_value=(47.0, -1.0)),
        catalog={
            "haies": MagicMock(
                hedges_to_remove=MagicMock(
                    return_value=[
                        MagicMock(
                            geometry=MagicMock(
                                wkt="MULTILINESTRING((-1.165924 49.320479, -1.147814 49.312645, -1.139402 49.314548))"
                            )
                        )
                    ]
                )
            )
        },
    )
    PerimeterFactory(
        regulations=[regulation],
        activation_map=france_map,
    )
    PerimeterFactory(
        regulations=[regulation],
        activation_map=france_map,
    )
    assert regulation.map
    assert len(regulation.map.entries) == 3
    assert regulation.map.entries[0].color == regulation.polygon_color
    assert regulation.map.entries[-1].color == "red"
    assert not regulation.map.display_marker_at_center
