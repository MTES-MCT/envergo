from django import forms
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Department
from envergo.moulinette.regulations import CriterionEvaluator


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
    final_surface = forms.IntegerField(
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
        final_surface = data.get("final_surface")

        # The user MUST provide the total final surface
        # However, in a previous version of the form, the user
        # would provide the existing surface and the created surface, and
        # the final surface was computed.
        # So we have to accomodate for bookmarked simulation with the old
        # data format

        # Both are missing
        if existing_surface is None and final_surface is None:
            self.add_error("final_surface", _("This field is required"))

        # Old version, project surface is missing
        elif final_surface is None:
            data["final_surface"] = created_surface + existing_surface

        # New version, project surface is provided
        # If existing_surface is missing, we compute it
        # If both values are somehow provided, we check that they are consistent
        else:
            if final_surface < created_surface:
                self.add_error(
                    "final_surface",
                    _("The total surface must be greater than the created surface"),
                )
            else:
                if existing_surface is None:
                    data["existing_surface"] = final_surface - created_surface
        return data


EMPTY_CHOICE = ("", "---------")


class MoulinetteDebugForm(forms.Form):
    """For debugging purpose.

    This form dynamically creates a field for every `CriterionEvaluator` subclass.
    """

    department = forms.ModelChoiceField(
        label=_("Department"),
        required=True,
        queryset=Department.objects.all(),
        to_field_name="department",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        criteria = [criterion for criterion in CriterionEvaluator.__subclasses__()]
        for criterion in criteria:
            field_name = f"{criterion.slug}"
            choices = [EMPTY_CHOICE] + list(zip(criterion.CODES, criterion.CODES))
            self.fields[field_name] = forms.ChoiceField(
                label=criterion.choice_label,
                choices=choices,
                required=False,
            )
