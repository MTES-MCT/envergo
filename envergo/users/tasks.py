from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from config.celery_app import app
from envergo.users.models import User
from envergo.utils.tools import get_base_url

LOGIN_SUBJECT = "Connexion à EnvErgo"


@app.task
def send_connection_email(user_email, body_template="emails/login_token.txt"):
    """Send a login email to the user.

    The email contains a token that can be used once to login.

    We use the default django token generator, that is usually used for
    password resets.
    """
    try:
        user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        # In case we could not find any valid user with the given email
        # we don't raise any exception, because we can't give any hints
        # about whether or not any particular email has an account
        # on our site.
        return

    user_uid = urlsafe_base64_encode(force_bytes(user.pk))
    login_token = default_token_generator.make_token(user)
    login_url = reverse("token_login", args=[user_uid, login_token])
    base_url = get_base_url()
    full_login_url = "{base_url}{url}".format(base_url=base_url, url=login_url)

    login_email_body = render_to_string(
        body_template,
        {
            "base_url": base_url,
            "user_name": user.full_name,
            "full_login_url": full_login_url,
        },
    )
    send_mail(
        subject=LOGIN_SUBJECT,
        body=login_email_body,
        recipient_list=[user.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        tags=["connexion", settings.ENV_NAME],
        fail_silently=False,
    )
