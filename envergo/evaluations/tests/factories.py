import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.evaluations.models import Criterion, Evaluation, Request
from envergo.geodata.tests.factories import ParcelFactory


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")

    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    created_surface = fuzzy.FuzzyInteger(25, 9999)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    result = "soumis"
    contact_email = factory.Sequence(lambda n: f"user_{n}@example.com")
    contact_md = "envergo@example.org"
    contact_html = "envergo@example.org"

    @factory.post_generation
    def criterions(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted is not None:
            for criterion in extracted:
                self.criterions.add(criterion)
        else:
            self.criterions.add(CriterionFactory(evaluation=self))


class CriterionFactory(DjangoModelFactory):
    class Meta:
        model = Criterion

    evaluation = factory.SubFactory(EvaluationFactory)
    probability = fuzzy.FuzzyInteger(1, 4)
    result = "soumis"
    criterion = "rainwater_runoff"
    description_md = factory.Faker("text")
    description_html = factory.Faker("text")


class RequestFactory(DjangoModelFactory):
    class Meta:
        model = Request

    reference = factory.Sequence(lambda n: f"ABC{n:03}")
    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    created_surface = fuzzy.FuzzyInteger(25, 10000)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    project_description = factory.Faker("text")
    contact_email = factory.Sequence(lambda n: f"user_{n}@example.com")

    @factory.post_generation
    def parcels(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for parcel in extracted:
                self.parcels.add(parcel)
        else:
            self.parcels.add(ParcelFactory())
