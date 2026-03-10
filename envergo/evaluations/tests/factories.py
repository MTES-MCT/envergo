import factory
from factory.django import DjangoModelFactory

from envergo.evaluations.models import (
    Evaluation,
    EvaluationSnapshot,
    EvaluationVersion,
    RegulatoryNoticeLog,
    Request,
    RequestFile,
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
    urbanism_department_emails = ["instructor@example.org"]
    project_owner_emails = ["sponsor1@example.org", "sponsor2@example.org"]

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
        created_surface = 1500
        final_surface = 3000
        moulinette_url = f"http://envergo/?created_surface={created_surface}&final_surface={final_surface}&lng=-1.646947&lat=47.696706"  # noqa
        return moulinette_url


class VersionFactory(DjangoModelFactory):
    class Meta:
        model = EvaluationVersion

    evaluation = factory.SubFactory(EvaluationFactory)
    created_by = factory.SubFactory("envergo.users.tests.factories.UserFactory")
    content = factory.Faker("text")
    published = False


class RequestFactory(DjangoModelFactory):
    class Meta:
        model = Request
        skip_postgeneration_save = True

    reference = factory.Sequence(lambda n: f"ABC{n:03}")
    address = factory.Sequence(lambda n: f"{n} rue de l'example, Testville")
    project_description = factory.Faker("text")
    user_type = "instructor"
    urbanism_department_emails = ["instructor@example.org"]
    project_owner_emails = ["sponsor1@example.org", "sponsor2@example.org"]


class RequestFileFactory(DjangoModelFactory):
    class Meta:
        model = RequestFile

    request = factory.SubFactory(RequestFactory)
    name = factory.Sequence(lambda n: f"file_{n}.pdf")
    file = factory.django.FileField(filename="file.pdf", data=b"Hello")


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


class EvaluationSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = EvaluationSnapshot

    evaluation = factory.SubFactory(EvaluationFactory)
    moulinette_url = factory.SelfAttribute("evaluation.moulinette_url")
    payload = factory.LazyAttribute(lambda obj: {"test": "data"})
