import logging

from crisp_api import Crisp
from crisp_api.errors.route import RouteError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

client = Crisp()
client.set_tier("plugin")
if settings.CRISP_TOKEN_ID and settings.CRISP_TOKEN_KEY:
    client.authenticate(settings.CRISP_TOKEN_ID, settings.CRISP_TOKEN_KEY)


def create_contact(email):
    if settings.ENV_NAME != "production":
        return

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
        if message == "people_exists":
            logger.info(f"CRISP contact already exists: {email}")
        else:
            raise e


def update_contacts_data(emails, reference, url):
    if settings.ENV_NAME != "production":
        return

    for email in emails:
        logger.info(f"Updating CRISP contact data for {email}")

        now = timezone.now()
        key = f"{reference}-{now:%y%m%d}"
        data = {"data": {key: url}}

        try:
            # First, we create the contact in the CRISP db. Then we save the useful data.
            create_contact(email)
            client.website.update_people_data(settings.CRISP_WEBSITE_ID, email, data)
        except Exception as e:
            logger.warning(f"Error while saving CRISP contact data {email}: {str(e)}")
