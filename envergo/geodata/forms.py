from django import forms
from django.utils.translation import gettext_lazy as _
from localflavor.fr.forms import FRDepartmentField

from envergo.geodata.models import Department


class DepartmentForm(forms.ModelForm):
    department = FRDepartmentField()

    class Meta:
        model = Department
        fields = ["department"]


class LatLngForm(forms.Form):
    lng = forms.DecimalField(
        label=_("Longitude"), required=True, max_digits=9, decimal_places=6
    )
    lat = forms.DecimalField(
        label=_("Latitude"), required=True, max_digits=9, decimal_places=6
    )
