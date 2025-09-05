import logging

from django.core.management.base import BaseCommand

from envergo.moulinette.models import MoulinetteTemplate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Post a message when a moulinette template has an obsolete key."

    def handle(self, *args, **options):

        moulinette_templates_with_envergo = MoulinetteTemplate.objects.filter(
            content__contains="EnvErgo"
        )
        count_templates = moulinette_templates_with_envergo.count()
        logger.info(f"Starting replace EnvErgo by Envergo {count_templates}")
        for moulinette_template in moulinette_templates_with_envergo:
            moulinette_template_new_content = moulinette_template.content.replace(
                "EnvErgo", "Envergo"
            )
            moulinette_templates_with_envergo.update(
                content=moulinette_template_new_content
            )
