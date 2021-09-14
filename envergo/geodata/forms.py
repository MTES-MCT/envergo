from django import forms
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Parcel


class ParcelForm(forms.ModelForm):
    commune = forms.CharField(
        label=_("Commune code"),
        max_length=5,
    )
    section = forms.CharField(
        label=_("Section"),
        max_length=2,
    )
    prefix = forms.CharField(label=_("Prefix"), max_length=3, required=False)
    order = forms.CharField(label=_("Parcel"), max_length=4)

    class Meta:
        model = Parcel
        fields = ("commune", "section", "prefix", "order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commune"].widget.attrs["placeholder"] = "34333"
        self.fields["section"].widget.attrs["placeholder"] = "BV"
        self.fields["prefix"].widget.attrs["placeholder"] = "000"
        self.fields["order"].widget.attrs["placeholder"] = "68"

    def clean_prefix(self):
        """The default prefix is often "000" and not provided at all."""
        prefix = self.cleaned_data["prefix"]
        return prefix or "000"

    def clean_section(self):
        section = self.cleaned_data["section"]
        return section.upper().zfill(2)


class BaseParcelFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = Parcel.objects.none()

    def clean(self):
        if any(self.errors):
            return

        new_forms = [f for f in self.extra_forms if f.has_changed()]
        if len(new_forms) == 0:
            raise forms.ValidationError(_("You must provide at least one parcel."))


ParcelFormSet = forms.modelformset_factory(
    Parcel,
    form=ParcelForm,
    formset=BaseParcelFormSet,
    extra=1,
)


class ParcelMapForm(forms.Form):
    address = forms.CharField(label=_("Address"))
