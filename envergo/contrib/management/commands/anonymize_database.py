from django.core.management import BaseCommand, CommandError
from faker import Faker
from tqdm import tqdm

from envergo.evaluations.models import Evaluation, RegulatoryNoticeLog, Request
from envergo.users.models import User

fake = Faker()


class Command(BaseCommand):
    help = "Anonymize the database by replacing all user data with random data. DO NOT USE IT IN PRODUCTION!"

    def add_arguments(self, parser):
        parser.add_argument(
            "env",
            help="The name of the environment.",
        )
        parser.add_argument(
            "-y",
            "--yes",
            help="Skip confirmation and run the command.",
            action="store_true",
        )

    def anonymize_model(self, model_class, qs, fields):
        self.stdout.write(f"Anonymizing {model_class.__name__} model...")

        total = qs.count()
        batch_size = 1000
        i = 0
        with tqdm(total=total) as pbar:
            while i < total:
                models = qs[i : i + batch_size].iterator()  # noqa
                to_update = []
                for model in models:
                    for name, action in fields:
                        setattr(model, name, action(model))
                    to_update.append(model)

                model_class.objects.bulk_update(to_update, [name for name, _ in fields])
                i += batch_size
                pbar.update(batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully anonymized the {model_class.__name__} model."
            )
        )

    def handle(self, *args, **options):
        if "env" not in options:
            raise CommandError("The environment url is required.")

        if options["env"] == "production" or options["env"] == "prod":
            raise CommandError("This command should NEVER be used in production.")

        if (
            not options["yes"]
            and input(
                "This command will permanently alter your data. Are you sure you want to proceed? (y/n)"
            )
            != "y"
        ):
            exit()

        self.anonymize_model(
            User,
            User.objects.filter(is_superuser=False),
            [("email", lambda x: fake.email()), ("name", lambda x: fake.name())],
        )
        self.anonymize_model(
            Evaluation,
            Evaluation.objects.all(),
            [
                ("contact_phone", lambda x: fake.phone_number()),
                ("contact_emails", lambda x: [fake.email()]),
                ("project_owner_emails", lambda x: [fake.email()]),
                ("project_owner_phone", lambda x: fake.phone_number()),
                ("project_owner_company", lambda x: fake.company()),
            ],
        )
        self.anonymize_model(
            Request,
            Request.objects.all(),
            [
                ("contact_phone", lambda x: fake.phone_number()),
                ("contact_emails", lambda x: [fake.email()]),
                ("project_owner_emails", lambda x: [fake.email()]),
                ("project_owner_phone", lambda x: fake.phone_number()),
            ],
        )
        self.anonymize_model(
            RegulatoryNoticeLog,
            RegulatoryNoticeLog.objects.all(),
            [
                ("frm", lambda x: fake.email()),
                ("to", lambda x: [fake.email()]),
                ("cc", lambda x: [fake.email()]),
                ("bcc", lambda x: [fake.email()]),
            ],
        )
