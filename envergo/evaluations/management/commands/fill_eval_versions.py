from django.core.management.base import BaseCommand
from django.db.models import Count

from envergo.evaluations.models import Evaluation
from envergo.users.models import User


# This is a temporary command. Remove once the versionning feature is done.
class Command(BaseCommand):
    help = "Make sure all evaluations has at least a version"

    def handle(self, *args, **options):
        thibault = User.objects.get(email="envergo@thibault.miximum.fr")
        evaluations = (
            Evaluation.objects.exclude(moulinette_url="")
            .annotate(nb_versions=Count("versions"))
            .exclude(nb_versions__gt=0)
        )
        self.stdout.write(f"Found {evaluations.count()} evaluations without versions")

        for eval in evaluations:
            version = eval.create_version(thibault)
            version.save()
