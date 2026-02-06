from datetime import date
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError
from django.db.backends.postgresql.psycopg_any import DateRange

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.geodata.tests.factories import DepartmentFactory, ZoneFactory
from envergo.moulinette.forms import MoulinetteFormAmenagement
from envergo.moulinette.models import (
    ConfigAmenagement,
    ConfigHaie,
    MoulinetteAmenagement,
    MoulinetteHaie,
)
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

    # Inactive config should be returned by has_config()
    ConfigAmenagementFactory(is_activated=False)
    moulinette = MoulinetteAmenagement(moulinette_data)
    assert moulinette.has_config()
    assert moulinette.is_valid(), moulinette.form_errors()


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


class TestConfigValidityDates:
    """Tests for the validity date mechanism on Config models."""

    def test_config_with_no_dates_is_always_valid(self):
        """A config with no date bounds is valid for any date."""
        dept = DepartmentFactory()
        config = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=None,
        )
        # Should be returned for any date
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2020, 1, 1)) == config
        )
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 15))
            == config
        )
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2030, 12, 31))
            == config
        )

    def test_config_valid_from_inclusive(self):
        """The lower bound of validity_range is inclusive (config is valid on that date)."""
        dept = DepartmentFactory()
        config = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), None, "[)"),
        )
        # Should NOT be returned before lower bound
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2024, 12, 31)) is None
        )
        # Should be returned ON lower bound (inclusive)
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 1, 1)) == config
        )
        # Should be returned after lower bound
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 15))
            == config
        )

    def test_config_valid_until_exclusive(self):
        """The upper bound of validity_range is exclusive (config is NOT valid on that date)."""
        dept = DepartmentFactory()
        config = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(None, date(2025, 6, 1), "[)"),
        )
        # Should be returned before upper bound
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 5, 31))
            == config
        )
        # Should NOT be returned ON upper bound (exclusive)
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 1)) is None
        )
        # Should NOT be returned after upper bound
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 2)) is None
        )

    def test_config_with_both_dates(self):
        """A config with both dates is only valid within the range [from, until)."""
        dept = DepartmentFactory()
        config = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), date(2025, 6, 1), "[)"),
        )
        # Before range
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2024, 12, 31)) is None
        )
        # At start (inclusive)
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 1, 1)) == config
        )
        # In range
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 3, 15))
            == config
        )
        # At end (exclusive)
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 1)) is None
        )
        # After range
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 7, 1)) is None
        )

    def test_multiple_configs_different_periods(self):
        """Multiple configs for the same department with non-overlapping periods."""
        dept = DepartmentFactory()
        config_2024 = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2024, 1, 1), date(2025, 1, 1), "[)"),
        )
        config_2025 = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), date(2026, 1, 1), "[)"),
        )
        # 2024 config should be returned for 2024 dates
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2024, 6, 15))
            == config_2024
        )
        # 2025 config should be returned for 2025 dates
        assert (
            ConfigAmenagement.objects.get_valid_config(dept, date(2025, 6, 15))
            == config_2025
        )


class TestConfigOverlapValidation:
    """Tests for the DB-level overlap ExclusionConstraint on Config models."""

    def test_overlap_rejected_between_configs(self):
        """Configs with overlapping dates should be rejected by the DB constraint."""
        dept = DepartmentFactory()
        ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), date(2025, 12, 31), "[)"),
        )
        overlapping = ConfigAmenagement(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 6, 1), date(2026, 6, 1), "[)"),
            lse_contact_ddtm="test",
            n2000_contact_ddtm_info="test",
            n2000_contact_ddtm_instruction="test",
            n2000_procedure_ein="test",
            evalenv_procedure_casparcas="test",
        )
        with pytest.raises(Exception):
            overlapping.save()

    def test_overlap_rejected_for_inactive_configs(self):
        """Inactive configs with overlapping dates should also be rejected."""
        dept = DepartmentFactory()
        ConfigAmenagementFactory(
            department=dept,
            is_activated=False,
            validity_range=DateRange(date(2025, 1, 1), date(2025, 12, 31), "[)"),
        )
        overlapping = ConfigAmenagement(
            department=dept,
            is_activated=False,
            validity_range=DateRange(date(2025, 6, 1), date(2026, 6, 1), "[)"),
            lse_contact_ddtm="test",
            n2000_contact_ddtm_info="test",
            n2000_contact_ddtm_instruction="test",
            n2000_procedure_ein="test",
            evalenv_procedure_casparcas="test",
        )
        with pytest.raises(Exception):
            overlapping.save()

    def test_overlap_rejected_between_active_and_inactive(self):
        """An inactive config cannot overlap with an active config."""
        dept = DepartmentFactory()
        ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), date(2025, 12, 31), "[)"),
        )
        overlapping = ConfigAmenagement(
            department=dept,
            is_activated=False,
            validity_range=DateRange(date(2025, 6, 1), date(2026, 6, 1), "[)"),
            lse_contact_ddtm="test",
            n2000_contact_ddtm_info="test",
            n2000_contact_ddtm_instruction="test",
            n2000_procedure_ein="test",
            evalenv_procedure_casparcas="test",
        )
        with pytest.raises(Exception):
            overlapping.save()

    def test_empty_range_not_allowed(self):
        """An empty validity_range (same lower and upper) is rejected by the DB constraint."""
        dept = DepartmentFactory()
        config = ConfigAmenagement(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 6, 1), date(2025, 6, 1), "[)"),
            lse_contact_ddtm="test",
            n2000_contact_ddtm_info="test",
            n2000_contact_ddtm_instruction="test",
            n2000_procedure_ein="test",
            evalenv_procedure_casparcas="test",
        )
        with pytest.raises(Exception):
            config.save()


class TestMoulinetteWithDate:
    """Tests for the Moulinette using date to select configs."""

    @pytest.mark.parametrize("footprint", [50])
    def test_moulinette_uses_date(self, moulinette_data):
        """Moulinette should use date to select the appropriate config."""
        dept = DepartmentFactory(department="44")
        config_2024 = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2024, 1, 1), date(2025, 1, 1), "[)"),
        )
        config_2025 = ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(date(2025, 1, 1), date(2026, 1, 1), "[)"),
        )
        moulinette_data["data"]["date"] = "2024-06-15"
        moulinette = MoulinetteAmenagement(moulinette_data)

        assert moulinette.config == config_2024

        moulinette_data["data"]["date"] = "2025-06-15"
        moulinette = MoulinetteAmenagement(moulinette_data)

        assert moulinette.config == config_2025

    @pytest.mark.parametrize("footprint", [50])
    def test_moulinette_defaults_to_today(self, moulinette_data):
        """Without date, Moulinette should use today's date."""
        dept = DepartmentFactory(department="44")
        ConfigAmenagementFactory(
            department=dept,
            is_activated=True,
            validity_range=None,
        )
        moulinette = MoulinetteAmenagement(moulinette_data)
        assert moulinette.config is not None
