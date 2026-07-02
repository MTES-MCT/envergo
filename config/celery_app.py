import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.conf import settings  # noqa

app = Celery("envergo")
app.config_from_object("django.conf:settings", namespace="CELERY")


class BaseTaskWithRetry(app.Task):
    """Default base task: always retry on failure, with capped backoff.

    Tasks routinely depend on flaky third parties (make.com, Mattermost,
    Démarches Simplifiées, IGN…). Rather than letting a transient failure drop
    the task on the floor, every task retries with exponential backoff. The
    capped `max_retries` prevents a genuinely broken (poison) message from
    retrying forever.
    """

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5


# Make every task retry by default, unless it overrides these attributes.
# This must run before autodiscover_tasks() so that every task picked up by
# the @app.task decorator inherits the retry policy.
app.Task = BaseTaskWithRetry

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
