from django.conf import settings
from django.urls import path
from redis.asyncio import Redis as RedisClient

from envergo.monitoring.views import EnvergoHealthCheckView

app_name = "monitoring"

# Checks which are expected to be "green" at any moment.
QUICK_CHECKS = [
    "health_check.Database",
    (
        "health_check.contrib.redis.Redis",
        {"client_factory": lambda: RedisClient.from_url(settings.CELERY_BROKER_URL)},
    ),
]

# Celery check is known to flicker on Scalingo.
# It is monitored differently to avoid noise, but we can check it manually if we need a diagnostic.
FULL_CHECKS = QUICK_CHECKS + ["health_check.contrib.celery.Ping"]

urlpatterns = [
    path(
        "full/",
        EnvergoHealthCheckView.as_view(
            checks=FULL_CHECKS,
        ),
        name="check_full",
    ),
    path(
        "quick/",
        EnvergoHealthCheckView.as_view(checks=QUICK_CHECKS),
        name="check_quick",
    ),
]
