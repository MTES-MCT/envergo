import json

import pytest
from django.db.models import JSONField
from django.forms.models import model_to_dict

from envergo.demarchenumerique.admin import DemarcheNumeriqueAdminForm
from envergo.demarchenumerique.tests.factories import DemarcheConfigFactory

DemarcheNumeriqueTestForm = DemarcheNumeriqueAdminForm

pytestmark = pytest.mark.django_db


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


class TestConfigDNDisplayFieldValidation:
    """Tests for the admin form validation on `display_fields`.

    When `demarche_numerique_number` is set, `display_fields` should have
    keys "organization", "city", "pacage" set with value.
    """

    def test_validation_when_demarche_numerique_number_is_set(self):
        """Form is not valid when city or organization or pacage are not set."""
        config = DemarcheConfigFactory()
        data = instance_to_form_data(config)
        data["pre_fill_config"] = "[]"
        form = DemarcheNumeriqueTestForm(data=data, instance=config)
        assert not form.is_valid()
        assert "display_fields" in form.errors

    def test_admin_form_invalid_when_pacage_missing(self):
        config = DemarcheConfigFactory(
            display_fields={
                "project_url": "ABC123",
                "city": "XYZ123",
                "organization": "XYZ456",
            }
        )
        data = instance_to_form_data(config)
        data["pre_fill_config"] = "[]"
        form = DemarcheNumeriqueTestForm(data=data, instance=config)
        assert not form.is_valid()
        assert "display_fields" in form.errors

    def test_admin_form_invalid_when_city_missing(self):
        config = DemarcheConfigFactory(
            display_fields={
                "project_url": "ABC123",
                "pacage": "XYZ789",
                "organization": "XYZ456",
            }
        )
        data = instance_to_form_data(config)
        data["pre_fill_config"] = "[]"
        form = DemarcheNumeriqueTestForm(data=data, instance=config)
        # THEN form is not valid
        assert not form.is_valid()
        assert "display_fields" in form.errors

    def test_admin_form_invalid_when_organization_missing(self):
        config = DemarcheConfigFactory(
            display_fields={
                "project_url": "ABC123",
                "pacage": "XYZ789",
                "city": "XYZ123",
            }
        )
        data = instance_to_form_data(config)
        data["pre_fill_config"] = "[]"
        form = DemarcheNumeriqueTestForm(data=data, instance=config)
        assert not form.is_valid()
        assert "display_fields" in form.errors

    def test_admin_form_valid_when_all_are_filled(self):
        config = DemarcheConfigFactory(
            display_fields={
                "project_url": "ABC123",
                "pacage": "XYZ789",
                "city": "XYZ123",
                "organization": "XYZ456",
            }
        )
        data = instance_to_form_data(config)
        data["pre_fill_config"] = "[]"
        form = DemarcheNumeriqueTestForm(data=data, instance=config)
        assert form.is_valid(), form.errors
