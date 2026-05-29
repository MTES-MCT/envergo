from django.apps import AppConfig


class PetitionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "envergo.petitions"
    verbose_name = "Guichet unique de la haie"

    def ready(self):
        import envergo.petitions.regulations.alignementarbres  # noqa
        import envergo.petitions.regulations.conditionnalitepac  # noqa
        import envergo.petitions.regulations.ep  # noqa
        import envergo.petitions.regulations.sites_proteges_haie  # noqa

        from . import signals  # noqa
