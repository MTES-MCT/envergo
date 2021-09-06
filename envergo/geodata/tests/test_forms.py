import pytest

from envergo.geodata.forms import ParcelForm

pytestmark = pytest.mark.django_db


@pytest.fixture
def parcel_data():
    return {
        "commune": "34333",
        "prefix": "000",
        "section": "BV",
        "order": "68",
    }


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
