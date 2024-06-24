import pytest

from envergo.evaluations.forms import WizardAddressForm
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.moulinette.tests.factories import MoulinetteConfigFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def form_data():
    return {
        "address": "123 rue de la Paix 44000 Nantes",
        "no_address": False,
        "application_number": "PC05412621D1029",
    }


@pytest.fixture(autouse=True)
def moulinette_config(loire_atlantique_department):  # noqa
    MoulinetteConfigFactory(
        department=loire_atlantique_department,
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )


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
