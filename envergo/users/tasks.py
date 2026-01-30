from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from config.celery_app import app
from envergo.users.models import User
from envergo.utils.mattermost import notify
from envergo.utils.tools import get_base_url, get_site_literal

REGISTER_SUBJECT = {
    "amenagement": "[Envergo] Activation de votre compte",
    "haie": "[Guichet unique de la haie] Activation de votre compte",
}


@app.task
def send_account_activation_email(user_email, side_id, activate_url):
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
    base_url = get_base_url(site.domain)
    full_activate_url = f"{base_url}{activate_url}"

    txt_template = f"{site_literal}/emails/activate_account.txt"
    html_template = f"{site_literal}/emails/activate_account.html"
    context = {
        "base_url": base_url,
        "user_name": user.name,
        "full_activate_url": full_activate_url,
    }
    subject = REGISTER_SUBJECT[site_literal]
    frm = settings.FROM_EMAIL[site_literal]["accounts"]

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


@app.task
def send_new_account_notification(user_id):
    """Warn admins of new haie account registrations.
    Only used for new accounts on GUH.

    TODO: fix base url if not on GUH
    """

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    user, domain = user.email.split("@")
    anon_email = f"{user[0]}***@{domain}"

    user_url = reverse("admin:users_user_change", args=[user_id])
    base_url = get_base_url(settings.ENVERGO_HAIE_DOMAIN)
    full_user_url = f"{base_url}{user_url}"

    message_body = render_to_string(
        "users/mattermost_new_account_notif.txt",
        context={"user_url": full_user_url, "anon_email": anon_email},
    )
    notify(message_body, "haie")
