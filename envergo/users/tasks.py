from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from config.celery_app import app
from envergo.users.models import User
from envergo.utils.auth import make_token_login_url
from envergo.utils.tools import get_base_url

LOGIN_SUBJECT = "[EnvErgo] Activation de votre compte"


@app.task
def send_account_activation_email(user_email, site_domain):
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

    login_url = make_token_login_url(user)
    base_url = get_base_url(site_domain)
    full_login_url = "{base_url}{url}".format(base_url=base_url, url=login_url)

    txt_template = "emails/activate_account.txt"
    html_template = "emails/activate_account.html"
    context = {
        "base_url": base_url,
        "user_name": user.name,
        "full_login_url": full_login_url,
    }

    txt_body = render_to_string(txt_template, context)
    html_body = render_to_string(html_template, context)
    send_mail(
        LOGIN_SUBJECT,
        txt_body,
        html_message=html_body,
        recipient_list=[user.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=False,
    )
