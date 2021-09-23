from django import forms
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Parcel


class ParcelForm(forms.ModelForm):
    commune = forms.CharField(
        label=_("Commune code"),
        help_text=_("5 chars long INSEE code"),
        max_length=5,
    )
    section = forms.CharField(
        label=_("Section"),
        help_text=_("One or two letters"),
        max_length=2,
    )
    prefix = forms.CharField(
        label=_("Prefix"),
        help_text=_("3 chars long number"),
        max_length=3,
        required=False,
    )
    order = forms.CharField(label=_("Parcel"), help_text=_("A number"), max_length=4)

    class Meta:
        model = Parcel
        fields = ("commune", "section", "prefix", "order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_prefix(self):
        """The default prefix is often "000" and not provided at all."""
        prefix = self.cleaned_data["prefix"]
        return prefix or "000"

    def clean_section(self):
        section = self.cleaned_data["section"]
        return section.upper().zfill(2)

    def has_changed(self):
        """Custom validation rule for forms with only the commune field.

        When a form in a formset is empty, it is just ignored.
        Well, since we autofill the commune field, we also ignore when
        this only field is set, so as to not block form submission.
        """

        if len(self.changed_data) == 1 and "commune" in self.changed_data:
            return False
        return super().has_changed()


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
