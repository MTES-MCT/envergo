from envergo.geodata.models import Department
from envergo.utils.tools import get_department_settings_form_url


def test_get_department_settings_form_url():
    department = Department(department="02")

    url = get_department_settings_form_url(department)

    assert url == "https://tally.so/r/Pd9b9e?departement=Aisne+%2802%29"
