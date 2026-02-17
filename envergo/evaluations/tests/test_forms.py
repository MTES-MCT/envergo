import pytest

from envergo.evaluations.forms import WizardAddressForm, WizardContactForm


@pytest.fixture
def form_data():
    return {
        "address": "123 rue de la Paix 44000 Nantes",
        "application_number": "PC05412621D1029",
    }


@pytest.fixture(autouse=True)
def _require_moulinette_config(moulinette_config):
    """Activate the shared moulinette_config fixture for all tests in this module."""
    pass


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


def test_prevent_storing_project_owner_details_when_we_should_not_send_him_the_eval():
    contact_data = {
        "user_type": "instructor",
        "project_owner_phone": "+33612345678",
        "project_owner_emails": ["test@test.com"],
        "send_eval_to_project_owner": False,
        "urbanism_department_emails": ["test@test.com"],
        "urbanism_department_phone": "+33612345678",
    }
    form = WizardContactForm(contact_data)
    assert form.is_valid()
    assert not form.cleaned_data.get("project_owner_phone")
    assert not form.cleaned_data.get("project_owner_emails")

    contact_data = {
        "user_type": "instructor",
        "project_owner_phone": "+33600000000",
        "project_owner_emails": ["peti@test.com"],
        "send_eval_to_project_owner": True,
        "urbanism_department_emails": ["instru@test.com"],
        "urbanism_department_phone": "+33612345678",
    }
    form = WizardContactForm(contact_data)
    assert form.is_valid()
    assert form.cleaned_data.get("project_owner_phone") == "+33600000000"
    assert form.cleaned_data.get("project_owner_emails") == ["peti@test.com"]

    contact_data = {
        "user_type": "petitioner",
        "project_owner_phone": "+33600000000",
        "project_owner_emails": ["peti@test.com"],
        "send_eval_to_project_owner": False,
        "urbanism_department_emails": ["instru@test.com"],
        "urbanism_department_phone": "+33612345678",
    }
    form = WizardContactForm(contact_data)
    assert form.is_valid()
    assert form.cleaned_data.get("project_owner_phone") == "+33600000000"
    assert form.cleaned_data.get("project_owner_emails") == ["peti@test.com"]
    assert not form.cleaned_data.get("urbanism_department_emails")
    assert not form.cleaned_data.get("urbanism_department_phone")
