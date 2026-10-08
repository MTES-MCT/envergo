from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import localtime

from envergo.users.models import User

# Leaves a genuine user time to click the activation link before we give up.
ACTIVATION_GRACE_PERIOD = timedelta(days=2)


class Command(BaseCommand):
    help = "Delete accounts that were never activated, most of them spam registrations"

    def handle(self, *args, **options):
        # Never having logged in tells abandoned signups apart from accounts
        # deactivated by an admin.
        cutoff = localtime() - ACTIVATION_GRACE_PERIOD
        unactivated_accounts = User.objects.filter(
            is_active=False, last_login__isnull=True, date_joined__lt=cutoff
        )

        deleted_count, _ = unactivated_accounts.delete()
        self.stdout.write(f"Deleted {deleted_count} unactivated accounts")
