from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    name = "envergo.evaluations"

    def ready(self):
        from . import signals  # noqa
