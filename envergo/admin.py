from django.contrib import admin
from django.contrib.admin.apps import AdminConfig


class EnvergoAdminConfig(AdminConfig):
    default_site = "envergo.admin.EnvergoAdminSite"


# Exclude those models from the main list, but don't disable the admin module entirely
EXCLUDED_MODELS = ("MoulinetteTemplate",)


class EnvergoAdminSite(admin.AdminSite):
    def get_app_list(self, request, app_label=None):
        """Reorder the apps in the admin site.

        By default, django admin apps are order alphabetically.

        To be more consistent with the actual worflow, we want the "Demande d'avis"
        app listed before the "Avis" one.

        And since django does not offer a simple way to order app, we have to tinker
        with the default app list, find the indexes of the two apps in the list,
        and swap them.
        """
        apps = super().get_app_list(request, app_label)

        # Find the index of the "evaluations" app in the list of top level apps
        evaluations = next(
            (
                index
                for (index, app) in enumerate(apps)
                if app["app_label"] == "evaluations"
            ),
            None,
        )
        if not evaluations:
            return apps

        # Find the indexes of the "Avis" and "Demande d'avis" models in the "evaluations" app
        avis_index = next(
            (
                index
                for (index, app) in enumerate(apps[evaluations]["models"])
                if app["object_name"] == "Evaluation"
            ),
            None,
        )
        demande_index = next(
            (
                index
                for (index, app) in enumerate(apps[evaluations]["models"])
                if app["object_name"] == "Request"
            ),
            None,
        )
        if avis_index is None or demande_index is None:
            return apps

        # And do the swap, python style
        (
            apps[evaluations]["models"][avis_index],
            apps[evaluations]["models"][demande_index],
        ) = (
            apps[evaluations]["models"][demande_index],
            apps[evaluations]["models"][avis_index],
        )

        # Now, we want to filter out some modules from the main list
        for app in apps:
            app["models"] = [
                model
                for model in app["models"]
                if model["object_name"] not in EXCLUDED_MODELS
            ]

        return apps
