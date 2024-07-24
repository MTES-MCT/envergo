import pytest
from django.contrib.sites.models import Site

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


@pytest.fixture(scope="session", autouse=True)
def update_default_site(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        Site.objects.create(domain="testserver", name="testserver")
