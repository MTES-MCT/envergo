import logging

from crisp_api import Crisp
from crisp_api.errors.route import RouteError
from django.conf import settings

logger = logging.getLogger(__name__)


def create_contacts(emails):
    client = Crisp()
    client.set_tier("plugin")
    client.authenticate(settings.CRISP_TOKEN_ID, settings.CRISP_TOKEN_KEY)

    for contact in emails:
        data = {
            "email": contact,
            "person": {"nickname": contact},
        }
        try:
            client.website.add_new_people_profile(settings.CRISP_WEBSITE_ID, data)
        except RouteError as e:
            error = e.args[0]
            message = error["message"]

            # If the error is that the contact already exists, we can safely ignore it
            if message != "people_exists":
                logger.warning(
                    f"Error while creating CRISP contact {contact}: {message}"
                )
