from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from envergo.moulinette.models import MoulinetteTemplate, get_all_template_keys
from envergo.utils.mattermost import notify


class Command(BaseCommand):
    help = "Post a message when a moulinette template has an obsolete key."

    def handle(self, *args, **options):
        obsolete_templates = MoulinetteTemplate.objects.exclude(
            key__in=[tuple[0] for tuple in get_all_template_keys()]
        ).select_related("config__department", "criterion")

        for obsolete_template in obsolete_templates:
            if obsolete_template.criterion:
                url = reverse(
                    "admin:moulinette_criterion_change",
                    args=[obsolete_template.criterion.id],
                )
                intro = f'Le critère "{obsolete_template.criterion.title}"[{obsolete_template.criterion.id}]'
            elif obsolete_template.config:
                url = reverse(
                    "admin:moulinette_configamenagement_change",
                    args=[obsolete_template.config.id],
                )
                config = obsolete_template.config
                intro = f'La config amènagement du département "{config.department}"[{config.id}]'
            else:
                raise NotImplementedError(
                    "This template is not linked to a criterion or a config"
                )

            ping = (
                f'ping {", ".join(settings.CONFIG_MATTERMOST_HANDLERS)}'
                if settings.CONFIG_MATTERMOST_HANDLERS
                else ""
            )

            message = dedent(
                f"""\
                {intro} référence un template obsolète : id={obsolete_template.id} clef="{obsolete_template.key}".
                Il faudrait soit :
                * le mettre à jour
                * le supprimer
                * s'assurer que la liste des templates disponibles est correcte
                [Admin django](https://envergo.beta.gouv.fr{url})
                {ping}
                """
            )

            notify(message)
