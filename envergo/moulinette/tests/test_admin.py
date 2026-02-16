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
from envergo.moulinette.models import ConfigAmenagement, ConfigHaie, Criterion
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    DCConfigHaieFactory,
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
        f.name
        for f in instance._meta.get_fields()
        if isinstance(f, JSONField)
    }
    for key in json_field_names:
        if key in data:
            data[key] = json.dumps(data[key])

    # HTML forms don't submit None
    return {k: v if v is not None else "" for k, v in data.items()}


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
