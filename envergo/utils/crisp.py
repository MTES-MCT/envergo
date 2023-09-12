import logging

from crisp_api import Crisp
from crisp_api.errors.route import RouteError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

client = Crisp()
client.set_tier("plugin")
client.authenticate(settings.CRISP_TOKEN_ID, settings.CRISP_TOKEN_KEY)


def create_contact(email):
    data = {
        "email": email,
        "person": {"nickname": email},
    }
    try:
        client.website.add_new_people_profile(settings.CRISP_WEBSITE_ID, data)
    except RouteError as e:
        error = e.args[0]
        message = error["message"]

        # If the error is that the contact already exists, we can safely ignore it
        if message != "people_exists":
            raise e


def update_contacts_data(emails, reference, url):
    for email in emails:
        try:
            create_contact(email)
            now = timezone.now()
            key = f"{reference}-{now:%Y-%m-%d}"
            data = {"data": {key: url}}
            client.website.update_people_data(settings.CRISP_WEBSITE_ID, email, data)
        except Exception as e:
            logger.warning(f"Error while updating CRISP contact data {email}: {str(e)}")
