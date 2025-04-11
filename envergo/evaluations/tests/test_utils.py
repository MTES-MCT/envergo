from envergo.evaluations.utils import extract_department_from_address_or_city_string


def test_extract_department_from_address_or_city_string():
    assert extract_department_from_address_or_city_string("Paris (75)") == "75"
    assert extract_department_from_address_or_city_string("Ajaccio (2A)") == "2A"
    assert (
        extract_department_from_address_or_city_string("Pointe-à-Pitre (971)") == "971"
    )
    assert (
        extract_department_from_address_or_city_string(
            "Rue des Grands Chênes 42600 Montbrison"
        )
        == "42"
    )
    assert (
        extract_department_from_address_or_city_string(
            "Appt B 15451 Rue des Grands Chênes 42600 Montbrison"
        )
        == "42"
    )
    assert extract_department_from_address_or_city_string("Tagata tsoin tsoin") is None
    assert extract_department_from_address_or_city_string("Paris (1234)") is None
    assert (
        extract_department_from_address_or_city_string(
            "Rue des Grands Chênes Montbrison"
        )
        is None
    )
