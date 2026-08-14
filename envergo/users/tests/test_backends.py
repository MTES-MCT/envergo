import pytest

from envergo.users.backends import AuthBackend

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


def test_admin_can_always_authenticate(admin_user):
    auth_backend = AuthBackend()
    assert auth_backend.user_can_authenticate(admin_user)


def test_haie_user_can_authenticate_only_on_haie(haie_user):
    auth_backend = AuthBackend()
    auth_backend.site_literal = "haie"
    assert auth_backend.user_can_authenticate(haie_user)

    auth_backend.site_literal = "amenagement"
    assert not auth_backend.user_can_authenticate(haie_user)


def test_amenagement_user_can_authenticate_only_on_amenagement(amenagement_user):
    auth_backend = AuthBackend()
    auth_backend.site_literal = "haie"
    assert not auth_backend.user_can_authenticate(amenagement_user)

    auth_backend.site_literal = "amenagement"
    assert auth_backend.user_can_authenticate(amenagement_user)
