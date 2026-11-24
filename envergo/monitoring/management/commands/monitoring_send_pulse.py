from django.conf import settings
from django.core.management.base import BaseCommand

from envergo.monitoring.tasks import send_pulse


class Command(BaseCommand):
    help = "Schedule a task to send a heartbeat to url saved in settings.HEALTH_CHECK_PULSE_URL"

    def handle(self, *args, **options):
        if settings.HEALTH_CHECK_PULSE_URL:
            send_pulse.delay()
