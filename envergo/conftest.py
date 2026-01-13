from unittest.mock import Mock, patch

import pytest
from django.contrib.sites.models import Site

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import DepartmentFactory
from envergo.users.models import User
from envergo.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def amenagement_user() -> User:
    return UserFactory(is_envergo_user=True)


@pytest.fixture
def haie_user() -> User:
    return UserFactory(is_haie_user=True)


@pytest.fixture
def inactive_haie_user_44() -> User:
    """Inactive haie user with dept 44"""
    haie_user_44 = UserFactory(is_haie_inactive_user=True)
    department_44 = DepartmentFactory.create()
    haie_user_44.departments.add(department_44)
    return haie_user_44


@pytest.fixture
def haie_user_44() -> User:
    """Haie user with dept 44"""
    haie_user_44 = UserFactory(is_haie_user=True)
    department_44 = DepartmentFactory.create()
    haie_user_44.departments.add(department_44)
    return haie_user_44


@pytest.fixture
def haie_instructor_44() -> User:
    """Haie user with dept 44 and is_instructor True"""
    haie_instructor_44 = UserFactory(is_haie_instructor=True)
    department_44 = DepartmentFactory.create()
    haie_instructor_44.departments.add(department_44)
    return haie_instructor_44


@pytest.fixture
def admin_user() -> User:
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def site() -> Site:
    return SiteFactory()


# Some views trigger a call to a remote API, and we want to make sure it is mocked
@pytest.fixture(autouse=True)
def mock_geo_api_data():
    with patch(
        "envergo.geodata.utils.get_data_from_coords", new=Mock()
    ) as mock_geo_data:
        mock_geo_data.return_value = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-1.3866392402397603, 47.14711855636099],
                },
                "properties": {
                    "id": "44070000AR0238",
                    "departmentcode": "44",
                    "municipalitycode": "070",
                    "oldmunicipalitycode": "000",
                    "districtcode": "000",
                    "section": "AR",
                    "sheet": "01",
                    "number": "0238",
                    "city": "La Haie-Fouassière",
                    "distance": 11,
                    "score": 0.9989,
                    "_type": "parcel",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-1.386865, 47.146822]},
                "properties": {
                    "type": "street",
                    "name": "Rue du Breil",
                    "postcode": "44690",
                    "citycode": "44070",
                    "city": "La Haie-Fouassière",
                    "oldcitycode": None,
                    "oldcity": None,
                    "context": "44, Loire-Atlantique, Pays de la Loire",
                    "importance": 0.49222,
                    "id": "44070_0553",
                    "x": 367734.49,
                    "y": 6681070.77,
                    "label": "Rue du Breil 44690 La Haie-Fouassière",
                    "distance": 27,
                    "score": 0.9973,
                    "_type": "address",
                },
            },
        ]
        yield mock_geo_data


@pytest.fixture(autouse=True)
def mock_get_current_site():
    # Create a mock site
    mock_site = Site()
    mock_site.domain = "www.example.com"
    mock_site.name = "example"

    # Use patch to replace get_current_site with your mock
    with patch(
        "django.contrib.sites.shortcuts.get_current_site", return_value=mock_site
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def update_default_site(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        SiteFactory(domain="testserver", name="testserver")
