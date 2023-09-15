from textwrap import shorten

from django import forms
from django.contrib import admin

from envergo.confs.models import TopBar


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
        if not all((avis_index, demande_index)):
            return apps

        # And do the swap, python style
        (
            apps[evaluations]["models"][avis_index],
            apps[evaluations]["models"][demande_index],
        ) = (
            apps[evaluations]["models"][demande_index],
            apps[evaluations]["models"][avis_index],
        )

        return apps


class TopBarAdminForm(forms.ModelForm):
    class Meta:
        model = TopBar
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message_md"].widget.attrs["rows"] = 5

    def clean_message_md(self):
        """Join the message in a single line."""
        message_md = self.cleaned_data["message_md"]
        lines = filter(None, message_md.splitlines())
        message_md = " ".join(lines)
        return message_md


@admin.register(TopBar)
class TopBarAdmin(admin.ModelAdmin):
    list_display = ["message_summary", "is_active", "updated_at"]
    fields = ("message_md", "is_active")
    form = TopBarAdminForm

    def message_summary(self, obj):
        return shorten(obj.message_md, width=50, placeholder="…")
