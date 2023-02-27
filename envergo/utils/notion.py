import logging

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def post_request(request, host):
    """Post a request to Notion."""

    secret = settings.NOTION_SECRET
    database_id = settings.NOTION_DATABASE_ID
    headers = {
        "Accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Authorization": f"Bearer {secret}",
    }

    request_url = reverse("admin:evaluations_request_change", args=[request.id])
    full_url = f"https://{host}{request_url}"
    now = timezone.now()

    data = {
        "parent": {"database_id": database_id},
        "properties": {
            "URL admin": {"url": full_url},
            "À envoyer au porteur": {"checkbox": request.send_eval_to_sponsor},
            "Résultat": {
                "multi_select": [
                    {
                        "name": "",
                    }
                ],
            },
            "Statut": {
                "select": {
                    "name": "1. À évaluer",
                },
            },
            "Description": {
                "type": "rich_text",
                "rich_text": [
                    {
                        "text": {"content": request.project_description},
                    }
                ],
            },
            "Adresse": {
                "rich_text": [
                    {
                        "text": {
                            "content": request.address,
                        },
                    }
                ],
            },
            "N° permis": {
                "rich_text": [
                    {
                        "text": {"content": request.application_number},
                    }
                ],
            },
            "Collectivité instructrice": {"select": None},
            "ID base SQL": {"number": request.id},
            "Date de réception": {
                "date": {"start": f"{now:%Y-%m-%d}", "end": None, "time_zone": None},
            },
            "Référence": {
                "rich_text": [
                    {
                        "text": {"content": request.reference},
                    }
                ],
            },
            "URL rappel réglementaire": {"url": None},
            "Name": {
                "title": [
                    {
                        "text": {"content": f"{request.id} - [nom à compléter]"},
                    }
                ],
            },
        },
    }

    api_url = "https://api.notion.com/v1/pages"
    response = requests.post(api_url, json=data, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error posting to Notion: {response.status_code}")
        logger.error(response.json())
