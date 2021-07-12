import factory
from factory.django import DjangoModelFactory

from envergo.evaluations.models import Evaluation


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")
