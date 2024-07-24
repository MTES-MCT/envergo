from factory.django import DjangoModelFactory

from envergo.evaluations.models import Evaluation


class SiteFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    domain = "testserver"
    name = "testserver"
