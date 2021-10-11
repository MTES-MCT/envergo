import re

import pytest
from django.urls import reverse

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

    mail_body = mailoutbox[0].body
    re_match = re.search(r"^https://[\w.-]*(.*)$", mail_body, re.MULTILINE)
    url = re_match.group(1)
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert res.wsgi_request.user.is_authenticated
