import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.evaluations.models import Evaluation


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")

    commune = factory.Sequence(lambda n: f"Ville {n:05}")
    created_surface = fuzzy.FuzzyInteger(25, 9999)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    global_probability = 2
    rainwater_runoff_probability = 2
    rainwater_runoff_impact = factory.Faker("text")
    flood_zone_probability = 2
    flood_zone_impact = factory.Faker("text")
    wetland_probability = 2
    wetland_impact = factory.Faker("text")
