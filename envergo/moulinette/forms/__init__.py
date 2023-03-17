from django import forms
from django.utils.translation import gettext_lazy as _


class MoulinetteForm(forms.Form):
    created_surface = forms.IntegerField(
        label=_("Surface created by the project"),
        required=True,
        min_value=0,
        help_text="Surface au sol nouvellement impactée par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
    )
    existing_surface = forms.IntegerField(
        label=_("Existing surface before the project"),
        required=False,
        min_value=0,
        help_text="Construction, voirie, espaces verts, remblais et bassins",
        widget=forms.HiddenInput,
    )
    project_surface = forms.IntegerField(
        label=_("Total surface at the end of the project"),
        required=False,
        min_value=0,
        help_text="Surface au sol impactée totale, y compris l'existant",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
    )
    address = forms.CharField(
        label=_("Search for the address to center the map"),
        help_text=_("Type in a few characters to see suggestions"),
        required=False,
    )
    lng = forms.DecimalField(
        label=_("Longitude"), required=True, max_digits=9, decimal_places=6
    )
    lat = forms.DecimalField(
        label=_("Latitude"), required=True, max_digits=9, decimal_places=6
    )

    def clean(self):
        data = super().clean()

        if self.errors:
            return data

        created_surface = data.get("created_surface")
        existing_surface = data.get("existing_surface")
        project_surface = data.get("project_surface")

        # The user MUST provide the total final surface
        # However, in a previous version of the form, the user
        # would provide the existing surface and the created surface, and
        # the final surface was computed.
        # So we have to accomodate for bookmarked simulation with the old
        # data format

        # Both are missing
        if existing_surface is None and project_surface is None:
            self.add_error("project_surface", _("This field is required"))

        # Old version, project surface is missing
        elif project_surface is None:
            data["project_surface"] = created_surface + existing_surface

        # New version, project surface is provided
        # If existing_surface is missing, we compute it
        # If both values are somehow provided, we check that they are consistent
        else:
            if project_surface < created_surface:
                self.add_error(
                    "project_surface",
                    _("The total surface must be greater than the created surface"),
                )
            else:
                if existing_surface is None:
                    data["existing_surface"] = project_surface - created_surface
        return data
