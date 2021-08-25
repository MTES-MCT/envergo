import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.evaluations.models import Criterion, Evaluation


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")

    commune = factory.Sequence(lambda n: f"Ville {n:05}")
    created_surface = fuzzy.FuzzyInteger(25, 9999)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    global_probability = 2
    contact_md = "envergo@example.org"
    contact_html = "envergo@example.org"

    @factory.post_generation
    def criterions(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for criterion in extracted:
                self.criterions.add(criterion)
        else:
            self.criterions.add(CriterionFactory(evaluation=self))


class CriterionFactory(DjangoModelFactory):
    class Meta:
        model = Criterion

    evaluation = factory.SubFactory(EvaluationFactory)
    probability = fuzzy.FuzzyInteger(1, 4)
    criterion = "rainwater_runoff"
    description_md = factory.Faker("text")
    description_html = factory.Faker("text")
