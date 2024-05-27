import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.evaluations.models import (
    Criterion,
    Evaluation,
    EvaluationVersion,
    RegulatoryNoticeLog,
    Request,
)


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation
        skip_postgeneration_save = True

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")
    request = factory.SubFactory("envergo.evaluations.tests.factories.RequestFactory")

    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    user_type = "instructor"
    contact_emails = ["instructor@example.org"]
    project_owner_emails = ["sponsor1@example.org", "sponsor2@example.org"]

    # Legacy data
    result = "soumis"
    created_surface = fuzzy.FuzzyInteger(25, 9999)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    contact_md = factory.Faker("text")

    @factory.post_generation
    def versions(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted is not None:
            for version in extracted:
                self.versions.add(version)
        else:
            self.versions.add(VersionFactory(evaluation=self))

    @factory.lazy_attribute
    def moulinette_url(self):
        moulinette_url = f"http://envergo/?created_surface={self.created_surface}&existing_surface={self.existing_surface}&lng=-1.30933&lat=47.11971"  # noqa
        return moulinette_url


class VersionFactory(DjangoModelFactory):
    class Meta:
        model = EvaluationVersion

    evaluation = factory.SubFactory(EvaluationFactory)
    created_by = factory.SubFactory("envergo.users.tests.factories.UserFactory")
    content = factory.Faker("text")


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
        skip_postgeneration_save = True

    reference = factory.Sequence(lambda n: f"ABC{n:03}")
    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    project_description = factory.Faker("text")
    user_type = "instructor"
    contact_emails = ["instructor@example.org"]
    project_owner_emails = ["sponsor1@example.org", "sponsor2@example.org"]


class RegulatoryNoticeLogFactory(DjangoModelFactory):
    class Meta:
        model = RegulatoryNoticeLog

    evaluation = factory.SubFactory(EvaluationFactory)
    sender = factory.SubFactory("envergo.users.tests.factories.UserFactory")
    frm = "from@example.com"
    to = ["to1@example.com", "to2@example.com"]
    cc = ["cc1@example.com", "admin@envergo"]
    bcc = []
    txt_body = factory.Faker("text")
    html_body = factory.Faker("text")
    subject = "Email subject"
    message_id = factory.Sequence(lambda n: f"message_{n}")
