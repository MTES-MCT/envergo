import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.evaluations.models import (
    Criterion,
    Evaluation,
    MailLog,
    RegulatoryNoticeLog,
    Request,
)
from envergo.geodata.tests.factories import ParcelFactory


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation
        skip_postgeneration_save = True

    application_number = factory.Sequence(lambda n: f"PC05112321D{n:04}")
    evaluation_file = factory.django.FileField(filename="eval.pdf", data=b"Hello")
    request = factory.SubFactory("envergo.evaluations.tests.factories.RequestFactory")

    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    created_surface = fuzzy.FuzzyInteger(25, 9999)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    result = "soumis"
    contact_emails = ["instructor@example.org"]
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

    @factory.lazy_attribute
    def moulinette_url(self):
        moulinette_url = f"http://envergo/?created_surface={self.created_surface}&existing_surface={self.existing_surface}&lng=-1.30933&lat=47.11971"  # noqa
        return moulinette_url


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
    created_surface = fuzzy.FuzzyInteger(25, 10000)
    existing_surface = fuzzy.FuzzyInteger(25, 9999)
    project_description = factory.Faker("text")
    user_type = "instructor"
    contact_emails = ["instructor@example.org"]
    project_sponsor_emails = ["sponsor1@example.org", "sponsor2@example.org"]

    @factory.post_generation
    def parcels(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for parcel in extracted:
                self.parcels.add(parcel)
        else:
            self.parcels.add(ParcelFactory())


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


class MailLogFactory(DjangoModelFactory):
    class Meta:
        model = MailLog

    regulatory_notice_log = factory.SubFactory(RegulatoryNoticeLogFactory)
    event = "opened"
    date = factory.Faker("date_time")
    recipient = "recipient@example.com"
