from textwrap import dedent

from django.conf import settings
from django.contrib.sites.models import Site
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

        for template in obsolete_templates:
            if template.criterion:
                url = reverse(
                    "admin:moulinette_criterion_change",
                    args=[template.criterion.id],
                )
                intro = (
                    f'Le critère "{template.criterion.title}"[{template.criterion.id}]'
                )
            elif template.config:
                url = reverse(
                    "admin:moulinette_configamenagement_change",
                    args=[template.config.id],
                )
                config = template.config
                intro = f'La config Aménagement du département "{config.department}"[{config.id}]'
            else:
                raise NotImplementedError(
                    "This template is not linked to a criterion or a config"
                )

            ping = (
                f'ping {", ".join(settings.CONFIG_MATTERMOST_HANDLERS)}'
                if settings.CONFIG_MATTERMOST_HANDLERS
                else ""
            )
            current_site = Site.objects.first()

            message = dedent(
                f"""\
                ### Anomalie de configuration

                {intro} référence un gabarit moulinette obsolète : id={template.id} clef="{template.key}".
                Il faudrait soit :
                * le mettre à jour
                * le supprimer
                * s'assurer que la liste des templates disponibles est correcte
                [Admin django](https://{current_site.domain}/{url})
                {ping}
                """
            )

            notify(message)
