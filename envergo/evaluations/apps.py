from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    name = "envergo.evaluations"
    verbose_name = "Avis Envergo"

    def ready(self):
        from . import signals  # noqa
