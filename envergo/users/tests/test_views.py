import re

import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


def test_password_reset_with_existing_email_does_send_an_email(
    client, user, mailoutbox
):
    login_url = reverse("password_reset")
    res = client.post(login_url, {"email": user.email})
    assert res.status_code == 302
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.subject == "Réinitialisation du mot de passe sur Envergo"
    assert mail.from_email == "comptes@amenagement.local"


def test_amenagement_register_view(client, mailoutbox):
    users = User.objects.all()
    assert users.count() == 0

    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": "test@example.com",
            "name": "Te St",
            "password1": "ViveLaTartiflette!",
            "password2": "ViveLaTartiflette!",
        },
    )
    assert res.status_code == 302
    assert len(mailoutbox) == 1
    assert mailoutbox[0].from_email == "comptes@amenagement.local"
    assert users.count() == 1

    user = users[0]
    assert not user.is_active

    mail_body = mailoutbox[0].body

    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200

    user.refresh_from_db()
    assert user.is_active
    assert user.access_amenagement
    assert not user.access_haie


def test_register_with_existing_email(amenagement_user, client, mailoutbox):
    """When existing user tries to register, no new user is created.

    We just send the activation email again."""
    users = User.objects.all()
    assert users.count() == 1

    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": amenagement_user.email,
            "name": "Te St",
            "password1": "ViveLaTartiflette!",
            "password2": "ViveLaTartiflette!",
        },
    )
    assert res.status_code == 302
    assert len(mailoutbox) == 1
    assert mailoutbox[0].from_email == "comptes@amenagement.local"
    assert users.count() == 1


def test_register_with_existing_email_and_other_errors(
    amenagement_user, client, mailoutbox
):
    """We never display the "this user already exists" error message."""

    users = User.objects.all()
    assert users.count() == 1

    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": amenagement_user.email,
            "name": "Te St",
            "password1": "A",
            "password2": "B",
        },
    )
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    content = res.content.decode()

    # Password mismatch error should be displayed
    assert "Les deux mots de passe ne correspondent pas" in content

    # Email error should NOT be displayed (security: don't reveal existing emails)
    assert "existe déjà" not in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_register_view(client, mailoutbox):
    users = User.objects.all()
    assert users.count() == 0

    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": "test@example.com",
            "name": "Te St",
            "password1": "ViveLaTartiflette!",
            "password2": "ViveLaTartiflette!",
        },
    )
    assert res.status_code == 302
    assert len(mailoutbox) == 1
    assert mailoutbox[0].from_email == "comptes@haie.local"
    assert users.count() == 1

    user = users[0]
    assert not user.is_active

    mail_body = mailoutbox[0].body
    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200

    user.refresh_from_db()
    assert user.is_active
    assert not user.access_amenagement
    assert user.access_haie


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_register_for_existing_amenagement_user(
    amenagement_user, client, mailoutbox
):
    """A user registered on one site can register on the other."""
    users = User.objects.all()
    assert not amenagement_user.access_haie
    assert users.count() == 1

    # Account already exists, trying to register
    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": amenagement_user.email,
            "name": "Te St",
            "password1": "ViveLaTartiflette!",
            "password2": "ViveLaTartiflette!",
        },
    )

    # Registration went well, account activation was sent
    assert res.status_code == 302
    assert len(mailoutbox) == 1
    assert mailoutbox[0].from_email == "comptes@haie.local"
    assert users.count() == 1

    amenagement_user.refresh_from_db()
    assert amenagement_user.is_active

    mail_body = mailoutbox[0].body
    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200

    amenagement_user.refresh_from_db()
    assert amenagement_user.is_active
    assert amenagement_user.access_amenagement
    assert amenagement_user.access_haie


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_register_duplicate_email_with_other_errors(
    amenagement_user, client, mailoutbox
):
    """The "email already exists" error is not displayed"""
    users = User.objects.all()
    assert not amenagement_user.access_haie
    assert users.count() == 1

    # Account already exists, trying to register
    register_url = reverse("register")
    res = client.post(
        register_url,
        {
            "email": amenagement_user.email,
            "name": "",
            "password1": "ViveLaTartiflette!",
            "password2": "ViveLaTartiflette!",
        },
    )

    # Registration went well, account activation was sent
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert users.count() == 1

    assert (
        "Un utilisateur avec cette adresse e-mail existe déjà"
        not in res.content.decode()
    )


def test_amenagement_login_on_amenagement_site(amenagement_user, client):
    assert amenagement_user.access_amenagement

    res = client.get("/")
    assert not res.wsgi_request.user.is_authenticated

    login_url = reverse("login")
    res = client.post(
        login_url, {"username": amenagement_user.email, "password": "password"}
    )
    assert res.status_code == 302
    assert res.wsgi_request.user.is_authenticated


def test_haie_login_on_amenagement_site(haie_user, client):
    assert not haie_user.access_amenagement

    res = client.get("/")
    assert not res.wsgi_request.user.is_authenticated

    login_url = reverse("login")
    res = client.post(login_url, {"username": haie_user.email, "password": "password"})
    assert res.status_code == 200
    assert not res.wsgi_request.user.is_authenticated


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_amenagement_login_on_haie_site(amenagement_user, client):
    assert not amenagement_user.access_haie

    res = client.get("/")
    assert not res.wsgi_request.user.is_authenticated

    login_url = reverse("login")
    res = client.post(
        login_url, {"username": amenagement_user.email, "password": "password"}
    )
    assert res.status_code == 200
    assert not res.wsgi_request.user.is_authenticated


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_login_on_haie_site(haie_user, client):
    assert haie_user.access_haie
    assert haie_user.is_active

    res = client.get("/")
    assert not res.wsgi_request.user.is_authenticated

    login_url = reverse("login")
    res = client.post(login_url, {"username": haie_user.email, "password": "password"})
    assert res.status_code == 302
    assert res.wsgi_request.user.is_authenticated
    assert res.url == "/projet/liste"


def test_user_access_without_otp(settings, user, client):
    """Frontend views require authentication but no OTP verification."""

    settings.ADMIN_OTP_REQUIRED = True
    dashboard_url = reverse("dashboard")

    # Make sure this url requires authentication
    res = client.get(dashboard_url, follow=False)
    assert res.status_code == 302
    assert res.url == "/comptes/connexion/?next=/avis/tableau-de-bord/"

    client.force_login(user)
    res = client.get(dashboard_url, follow=False)
    assert res.status_code == 200

    request_user = res.context["user"]
    assert not request_user.is_verified()


def test_admin_access_requires_otp(settings, admin_client):
    """Admin access requires opt verification."""
    settings.ADMIN_OTP_REQUIRED = True
    admin_url = reverse("admin:index")

    res = admin_client.get(admin_url, follow=False)
    assert res.status_code == 302
    assert res.url == "/admin/login/?next=/admin/"


def test_otp_can_be_deactivated(settings, admin_client):
    """Otp verification can be deactivated."""

    settings.ADMIN_OTP_REQUIRED = False
    admin_url = reverse("admin:index")

    res = admin_client.get(admin_url, follow=False)
    assert res.status_code == 200
