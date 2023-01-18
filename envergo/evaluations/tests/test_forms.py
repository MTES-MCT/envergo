import pytest

from envergo.evaluations.forms import WizardAddressForm


@pytest.fixture
def form_data():
    return {
        "address": "123 rue de la Paix",
        "no_address": False,
        "application_number": "PC05412621D1029",
    }


def test_wizard_form_with_address_is_valid(form_data):
    form = WizardAddressForm(form_data)
    assert form.is_valid()


def test_wizard_form_without_address_is_invalid(form_data):
    form_data["address"] = ""
    form = WizardAddressForm(form_data)
    assert not form.is_valid()

    del form_data["address"]
    form = WizardAddressForm(form_data)
    assert not form.is_valid()


def test_wizard_form_when_address_is_not_required_is_valid(form_data):
    form_data["address"] = ""
    form_data["no_address"] = True
    form = WizardAddressForm(form_data)
    assert form.is_valid()
