import pytest
from django.contrib.sites.models import Site

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.users.models import User
from envergo.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def admin_user() -> User:
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture(autouse=True)
def site() -> Site:
    return SiteFactory()
