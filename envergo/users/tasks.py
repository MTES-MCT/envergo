from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string

from config.celery_app import app
from envergo.users.models import User
from envergo.utils.auth import make_activate_account_url
from envergo.utils.tools import get_base_url, get_site_literal

REGISTER_SUBJECT = {
    "amenagement": "[EnvErgo] Activation de votre compte",
    "haie": "[Guichet unique de la haie] Activation de votre compte",
}


@app.task
def send_account_activation_email(user_email, side_id):
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

    try:
        site = Site.objects.get(id=side_id)
    except Site.DoesNotExist:
        return

    site_literal = get_site_literal(site)
    activate_url = make_activate_account_url(user)
    base_url = get_base_url(site.domain)
    full_activate_url = "{base_url}{url}".format(base_url=base_url, url=activate_url)

    txt_template = f"{site_literal}/emails/activate_account.txt"
    html_template = f"{site_literal}/emails/activate_account.html"
    context = {
        "base_url": base_url,
        "user_name": user.name,
        "full_activate_url": full_activate_url,
    }
    subject = REGISTER_SUBJECT[site_literal]
    frm = settings.SITE_FROM_EMAIL[site_literal]

    txt_body = render_to_string(txt_template, context)
    html_body = render_to_string(html_template, context)
    send_mail(
        subject,
        txt_body,
        html_message=html_body,
        recipient_list=[user.email],
        from_email=frm,
        fail_silently=False,
    )
