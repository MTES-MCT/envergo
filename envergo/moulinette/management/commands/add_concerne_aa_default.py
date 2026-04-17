from django.core.management.base import BaseCommand

from envergo.moulinette.models import Criterion


class Command(BaseCommand):
    help = 'Add concerne_aa = "non" to Natura2000Haie criteria missing it'

    def handle(self, *args, **options):
        qs = Criterion.objects.filter(
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
        ).exclude(evaluator_settings__has_key="concerne_aa")

        count = qs.count()
        if count == 0:
            self.stdout.write("No criteria to update.")
            return

        to_update = []
        for criterion in qs:
            if not criterion.evaluator_settings:
                criterion.evaluator_settings = {}
            criterion.evaluator_settings["concerne_aa"] = "non"
            to_update.append(criterion)

        Criterion.objects.bulk_update(to_update, ["evaluator_settings"])

        self.stdout.write(f"Updated {count} criteria.")
