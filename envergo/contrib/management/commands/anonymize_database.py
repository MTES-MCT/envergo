import os

from django.core.management import BaseCommand, CommandError
from faker import Faker
from tqdm import tqdm

from envergo.evaluations.models import Evaluation, RegulatoryNoticeLog, Request
from envergo.tchap.models import TchapCredential
from envergo.users.models import User

fake = Faker()


class Command(BaseCommand):
    help = "Anonymize the database by replacing all user data with random data. DO NOT USE IT IN PRODUCTION!"

    def add_arguments(self, parser):
        parser.add_argument(
            "-y",
            "--yes",
            help="Skip confirmation and run the command.",
            action="store_true",
        )

    def anonymize_model(self, qs, fields):
        model_class = qs.model
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

    def purge_tchap_credentials(self):
        """Drop the Tchap bot session instead of anonymizing it.

        The row holds the bot's access token and its olm private keys, which no
        fake value can stand in for: keeping a copy here would let this
        environment post as the bot in the real Tchap rooms and decrypt what is
        shared with it.
        """
        self.stdout.write("Purging TchapCredential model...")
        deleted, _ = TchapCredential.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully purged {deleted} Tchap credential(s).")
        )

    def handle(self, *args, **options):
        env_name = os.getenv("ENV_NAME")
        self.stdout.write(f"ENV_NAME: {env_name}")
        if env_name not in ["staging", "development", "dev", "local"]:
            raise CommandError(
                "This command should NEVER be used in production. "
                "You can only use it in staging or development environments "
                "by setting the ENV_NAME environment variable to 'staging' or 'development'."
            )

        if (
            not options["yes"]
            and input(
                "This command will permanently alter your data. Are you sure you want to proceed? (y/n)"
            )
            != "y"
        ):
            exit()

        self.anonymize_model(
            User.objects.filter(is_staff=False),
            [("email", lambda x: fake.unique.email()), ("name", lambda x: fake.name())],
        )
        self.anonymize_model(
            Evaluation.objects.all(),
            [
                ("urbanism_department_phone", lambda x: fake.phone_number()),
                ("urbanism_department_emails", lambda x: [fake.email()]),
                ("project_owner_emails", lambda x: [fake.email()]),
                ("project_owner_phone", lambda x: fake.phone_number()),
                ("project_owner_company", lambda x: fake.company()),
            ],
        )
        self.anonymize_model(
            Request.objects.all(),
            [
                ("urbanism_department_phone", lambda x: fake.phone_number()),
                ("urbanism_department_emails", lambda x: [fake.email()]),
                ("project_owner_emails", lambda x: [fake.email()]),
                ("project_owner_phone", lambda x: fake.phone_number()),
            ],
        )
        self.anonymize_model(
            RegulatoryNoticeLog.objects.all(),
            [
                ("frm", lambda x: fake.email()),
                ("to", lambda x: [fake.email()]),
                ("cc", lambda x: [fake.email()]),
                ("bcc", lambda x: [fake.email()]),
            ],
        )
        self.purge_tchap_credentials()
