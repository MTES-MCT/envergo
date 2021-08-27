from django import forms

from envergo.geodata.models import Parcel


class ParcelForm(forms.ModelForm):
    class Meta:
        model = Parcel
        fields = ("commune", "section", "prefix", "order")


ParcelFormSet = forms.modelformset_factory(Parcel, form=ParcelForm, extra=3)
