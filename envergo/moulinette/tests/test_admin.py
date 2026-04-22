import datetime
import json

import pytest
from django.db.models import JSONField
from django.forms import modelform_factory
from django.forms.models import model_to_dict
from psycopg.types.range import DateRange as PsycopgDateRange

from envergo.geodata.tests.factories import MapFactory
from envergo.moulinette.admin import (
    ConfigAmenagementForm,
    ConfigHaieAdminForm,
    CriterionAdminForm,
)
from envergo.moulinette.models import (
    AaL3503Handling,
    ConfigAmenagement,
    ConfigHaie,
    Criterion,
)
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    DCConfigHaieFactory,
    RUConfigHaieFactory,
)

pytestmark = pytest.mark.django_db

# CriterionAdminForm and ConfigAmenagementForm lack an inner Meta class —
# Django admin normally supplies one via modelform_factory. We do the same here
# so the forms can be instantiated directly in tests.
CriterionTestForm = modelform_factory(
    Criterion, form=CriterionAdminForm, fields="__all__"
)
ConfigAmenagementTestForm = modelform_factory(
    ConfigAmenagement, form=ConfigAmenagementForm, fields="__all__"
)
# ConfigHaieAdminForm already has its own Meta class.
ConfigHaieTestForm = ConfigHaieAdminForm


def instance_to_form_data(instance):
    """Build form POST data from a model instance.

    Uses model_to_dict so that new required fields added to the model are
    automatically included (as long as the factory provides them). Handles
    DateRangeField splitting for RangeWidget and JSONField serialization.
    """
    data = model_to_dict(instance)

    # DateRangeField uses RangeWidget with _0/_1 suffixed sub-fields
    vr = data.pop("validity_range", None)
    data["validity_range_0"] = vr.lower.isoformat() if vr and vr.lower else ""
    data["validity_range_1"] = vr.upper.isoformat() if vr and vr.upper else ""

    # JSONField values need string serialization for form widgets
    json_field_names = {
        f.name for f in instance._meta.get_fields() if isinstance(f, JSONField)
    }
    for key in json_field_names:
        if key in data:
            data[key] = json.dumps(data[key])

    # HTML forms don't submit None
    return {k: v if v is not None else "" for k, v in data.items()}


def update_data_jsonfield_with_new_entry(data, field_name, dict_update):
    """Updates data json field "field_name" with new entry"""
    json_field = json.loads(data[field_name])
    json_field.update(dict_update)
    data[field_name] = json.dumps(json_field)
    return data


class TestCriterionOverlapValidation:
    def test_overlap_shows_admin_link(self):
        """When a new criterion overlaps an existing one, the error contains an admin link."""
        existing = CriterionFactory(
            validity_range=PsycopgDateRange(
                datetime.date(2024, 1, 1), datetime.date(2025, 1, 1)
            ),
        )

        new = Criterion(
            evaluator=existing.evaluator,
            activation_map=existing.activation_map,
            regulation=existing.regulation,
            perimeter=existing.perimeter,
        )
        data = instance_to_form_data(existing)
        data["validity_range_0"] = "2024-06-01"
        data["validity_range_1"] = "2025-06-01"

        form = CriterionTestForm(data=data, instance=new)
        assert not form.is_valid()

        error_html = str(form.errors)
        assert "<a href=" in error_html
        assert str(existing.pk) in error_html

    def test_overlap_with_null_range(self):
        """An existing criterion with no validity range conflicts with any same-identity criterion."""
        existing = CriterionFactory(validity_range=None)

        new = Criterion(
            evaluator=existing.evaluator,
            activation_map=existing.activation_map,
            regulation=existing.regulation,
            perimeter=existing.perimeter,
        )
        data = instance_to_form_data(existing)
        data["validity_range_0"] = "2024-01-01"
        data["validity_range_1"] = "2025-01-01"

        form = CriterionTestForm(data=data, instance=new)
        assert not form.is_valid()

        error_html = str(form.errors)
        assert "<a href=" in error_html

    def test_no_false_positive_different_identity(self):
        """Overlapping dates but different identity fields should not raise an error."""
        existing = CriterionFactory(
            validity_range=PsycopgDateRange(
                datetime.date(2024, 1, 1), datetime.date(2025, 1, 1)
            ),
        )

        # Different activation_map → different identity
        other_map = MapFactory()
        new = Criterion(
            evaluator=existing.evaluator,
            activation_map=other_map,
            regulation=existing.regulation,
            perimeter=existing.perimeter,
        )
        data = instance_to_form_data(existing)
        data["activation_map"] = other_map.pk
        data["validity_range_0"] = "2024-06-01"
        data["validity_range_1"] = "2025-06-01"

        form = CriterionTestForm(data=data, instance=new)
        assert form.is_valid(), form.errors

    def test_editing_existing_object_no_self_overlap(self):
        """Editing an existing criterion without changing dates should not trigger self-overlap."""
        existing = CriterionFactory(
            validity_range=PsycopgDateRange(
                datetime.date(2024, 1, 1), datetime.date(2025, 1, 1)
            ),
        )

        data = instance_to_form_data(existing)
        form = CriterionTestForm(data=data, instance=existing)
        assert form.is_valid(), form.errors

    def test_check_constraint_still_works(self):
        """The non-empty range CheckConstraint should still fire via _post_clean."""
        criterion = CriterionFactory(validity_range=None)
        data = instance_to_form_data(criterion)
        # An empty range (same start and end) violates the CheckConstraint
        data["validity_range_0"] = "2024-01-01"
        data["validity_range_1"] = "2024-01-01"

        form = CriterionTestForm(data=data, instance=criterion)
        assert not form.is_valid()


class TestConfigAmenagementOverlapValidation:
    def test_overlap_shows_admin_link(self):
        """When a new config overlaps an existing one, the error contains an admin link."""
        existing = ConfigAmenagementFactory(
            validity_range=PsycopgDateRange(
                datetime.date(2024, 1, 1), datetime.date(2025, 1, 1)
            ),
        )

        new = ConfigAmenagement(department=existing.department)
        data = instance_to_form_data(existing)
        data["validity_range_0"] = "2024-06-01"
        data["validity_range_1"] = "2025-06-01"

        form = ConfigAmenagementTestForm(data=data, instance=new)
        assert not form.is_valid()

        error_html = str(form.errors)
        assert "<a href=" in error_html
        assert str(existing.pk) in error_html


class TestConfigHaieOverlapValidation:
    def test_overlap_shows_admin_link(self):
        """When a new config overlaps an existing one, the error contains an admin link."""
        existing = DCConfigHaieFactory(
            validity_range=PsycopgDateRange(
                datetime.date(2024, 1, 1), datetime.date(2025, 1, 1)
            ),
        )

        new = ConfigHaie(department=existing.department)
        data = instance_to_form_data(existing)
        data["validity_range_0"] = "2024-06-01"
        data["validity_range_1"] = "2025-06-01"

        form = ConfigHaieTestForm(data=data, instance=new)
        assert not form.is_valid()

        error_html = str(form.errors)
        assert "<a href=" in error_html
        assert str(existing.pk) in error_html


class TestConfigHaieAaL3503FormValidation:
    """Tests for the admin form validation of AA L350-3 fields.

    When single_procedure is active, the chosen handling mode determines which
    companion field is required. These tests verify that clean() surfaces the
    right errors on the right fields.
    """

    def build_form_data(self, instance, **overrides):
        """Build valid form data from a factory instance, then apply overrides.

        Clears demarche_simplifiee_pre_fill_config to avoid unrelated validation
        failures (the factory's pre-fill references form fields that require
        regulation fixtures).
        """
        data = instance_to_form_data(instance)
        data["demarche_simplifiee_pre_fill_config"] = "[]"
        data.update(overrides)
        return data

    def test_third_party_form_without_url_is_invalid(self):
        """Form rejects third-party mode with empty URL when single_procedure is on."""
        instance = RUConfigHaieFactory()
        data = self.build_form_data(
            instance,
            aa_l3503_handling=AaL3503Handling.THIRD_PARTY_FORM,
            aa_l3503_form_url="",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert not form.is_valid()
        assert "aa_l3503_form_url" in form.errors

    def test_third_party_form_with_url_is_valid(self):
        """Form accepts third-party mode with a URL when single_procedure is on."""
        instance = RUConfigHaieFactory()
        data = self.build_form_data(
            instance,
            aa_l3503_handling=AaL3503Handling.THIRD_PARTY_FORM,
            aa_l3503_form_url="https://example.com/form",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert form.is_valid(), form.errors

    def test_not_handled_without_contact_is_valid(self):
        """Form accepts not-handled mode with empty contact (contact info is optional)."""
        instance = RUConfigHaieFactory()
        data = self.build_form_data(
            instance,
            aa_l3503_handling=AaL3503Handling.NOT_HANDLED,
            aa_l3503_contact_info="",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert form.is_valid(), form.errors

    def test_not_handled_with_contact_is_valid(self):
        """Form accepts not-handled mode with contact info when single_procedure is on."""
        instance = RUConfigHaieFactory()
        data = self.build_form_data(
            instance,
            aa_l3503_handling=AaL3503Handling.NOT_HANDLED,
            aa_l3503_contact_info="<p>Contactez le service</p>",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert form.is_valid(), form.errors

    def test_portal_valid_without_url_or_contact(self):
        """Form accepts portal mode without URL or contact info."""
        instance = RUConfigHaieFactory()
        data = self.build_form_data(
            instance,
            aa_l3503_handling=AaL3503Handling.PORTAL,
            aa_l3503_form_url="",
            aa_l3503_contact_info="",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert form.is_valid(), form.errors

    def test_no_validation_when_single_procedure_off(self):
        """Form skips AA L350-3 validation when single_procedure is False."""
        instance = DCConfigHaieFactory()
        data = self.build_form_data(
            instance,
            single_procedure=False,
            aa_l3503_handling=AaL3503Handling.NOT_HANDLED,
            aa_l3503_contact_info="",
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert form.is_valid(), form.errors


class TestConfigHaieDNDisplayFieldValidation:
    """Tests for the admin form validation on `demarches_simplifiees_display_fields`.

    When `demarche_simplifiee_number` is set, `demarches_simplifiees_display_fields` should have
    keys "organization", "city", "pacage" set with value.
    """

    def test_validation_when_demarche_simplifiee_number_is_set(self):
        """Form skips AA L350-3 validation when single_procedure is False."""
        instance = DCConfigHaieFactory()
        data = instance_to_form_data(instance)
        data["demarche_simplifiee_pre_fill_config"] = "[]"
        form = ConfigHaieTestForm(data=data, instance=instance)
        assert not form.is_valid()
        assert "demarches_simplifiees_display_fields" in form.errors

        # WHEN only city is set in `demarches_simplifiees_display_fields`
        data = update_data_jsonfield_with_new_entry(
            data, "demarches_simplifiees_display_fields", {"city": "XYZ123"}
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        # THEN form is not valid
        assert not form.is_valid()
        assert "demarches_simplifiees_display_fields" in form.errors

        # WHEN only city and organization are set in `demarches_simplifiees_display_fields`
        data = update_data_jsonfield_with_new_entry(
            data, "demarches_simplifiees_display_fields", {"organization": "XYZ456"}
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        # THEN form is not valid
        assert not form.is_valid()
        assert "demarches_simplifiees_display_fields" in form.errors

        # WHEN city, organization and pacate are set in `demarches_simplifiees_display_fields`
        data = update_data_jsonfield_with_new_entry(
            data, "demarches_simplifiees_display_fields", {"pacage": "XYZ789"}
        )
        form = ConfigHaieTestForm(data=data, instance=instance)
        # THEN form is valid
        assert form.is_valid(), form.errors
