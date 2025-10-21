from django.apps import AppConfig


class PetitionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "envergo.petitions"

    def ready(self):
        import envergo.petitions.regulations.alignementarbres  # noqa
        import envergo.petitions.regulations.conditionnalitepac  # noqa
        import envergo.petitions.regulations.ep  # noqa
        import envergo.petitions.regulations.natura2000_haie  # noqa
        import envergo.petitions.regulations.reserves_naturelles  # noqa
        import envergo.petitions.regulations.urbanisme_haie  # noqa
