import re

import pytest
from django.urls import reverse

from envergo.users.models import User

pytestmark = pytest.mark.django_db


def test_password_reset_with_existing_email_does_send_an_email(
    client, user, mailoutbox
):
    login_url = reverse("password_reset")
    res = client.post(login_url, {"email": user.email})
    assert res.status_code == 302
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.subject == "Réinitialisation du mot de passe sur EnvErgo"


def test_login_email_token_works(client, user, mailoutbox):
    login_url = reverse("password_reset")
    res = client.post(login_url, {"email": user.email})
    assert not res.wsgi_request.user.is_authenticated
    assert len(mailoutbox) == 1

    mail_body = mailoutbox[0].body
    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert res.wsgi_request.user.is_authenticated

    user.refresh_from_db()
    assert user.is_active


def test_register_view_works(client, mailoutbox):
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
    assert users.count() == 1

    user = users[0]
    assert not user.is_active

    mail_body = mailoutbox[0].body
    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert res.wsgi_request.user.is_authenticated

    user.refresh_from_db()
    assert user.is_active
