import pytest

from envergo.geodata.forms import ParcelForm, ParcelFormSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def parcel_data():
    return {
        "commune": "34333",
        "prefix": "000",
        "section": "BV",
        "order": "68",
    }


@pytest.fixture
def formset_data():
    data = {
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-commune": "34333",
        "form-0-section": "BV",
        "form-0-prefix": "000",
        "form-0-order": "68",
        "form-1-commune": "34333",
        "form-1-section": "BV",
        "form-1-prefix": "000",
        "form-1-order": "68",
    }
    return data


def test_form_is_valid(parcel_data):
    form = ParcelForm(data=parcel_data)
    assert form.is_valid()

    parcel = form.save()
    assert parcel.reference == "34333000BV0068"


def test_prefix_is_optional(parcel_data):
    parcel_data["prefix"] = ""
    form = ParcelForm(data=parcel_data)
    assert form.is_valid()
    assert form.cleaned_data["prefix"] == "000"

    parcel = form.save()
    assert parcel.reference == "34333000BV0068"


def test_section_can_be_one_letter(parcel_data):
    parcel_data["section"] = "A"
    form = ParcelForm(data=parcel_data)
    assert form.is_valid()
    assert form.cleaned_data["section"] == "0A"

    parcel = form.save()
    assert parcel.reference == "343330000A0068"


def test_section_can_be_lowercase(parcel_data):
    parcel_data["section"] = "a"
    form = ParcelForm(data=parcel_data)
    assert form.is_valid()
    assert form.cleaned_data["section"] == "0A"


def test_section_can_be_lowercase_2(parcel_data):
    parcel_data["section"] = "aa"
    form = ParcelForm(data=parcel_data)
    assert form.is_valid()
    assert form.cleaned_data["section"] == "AA"

    parcel = form.save()
    assert parcel.reference == "34333000AA0068"


def test_order_must_be_an_int(parcel_data):
    parcel_data["order"] = "a"
    form = ParcelForm(data=parcel_data)
    assert not form.is_valid()


def test_formset_is_valid(formset_data):
    formset = ParcelFormSet(data=formset_data)
    assert formset.is_valid()


def test_formset_ignores_forms_with_only_commune(formset_data):
    """Test the custom parcel empty form validation.

    When a form in a formset is empty, it is just ignored.
    Well, since we autofill the commune field, we also ignore when
    this only field is set, so as to not block form submission.
    """
    formset = ParcelFormSet(data=formset_data)
    formset_data.update(
        {
            "form-TOTAL_FORMS": "3",
            "form-2-commune": "34333",
        }
    )
    assert formset.is_valid()
