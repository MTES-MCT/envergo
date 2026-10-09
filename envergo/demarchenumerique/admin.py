from django import forms
from django.contrib import admin
from django.template.loader import render_to_string

from envergo.demarchenumerique.models import DemarcheConfig
from envergo.utils.widgets import JSONWidget


class DemarcheNumeriqueAdminForm(forms.ModelForm):
    class Meta:
        model = DemarcheConfig
        fields = "__all__"
        widgets = {
            "pre_fill_config": JSONWidget(attrs={"rows": 20, "cols": 80}),
            "display_fields": JSONWidget(attrs={"rows": 20, "cols": 80}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pre_fill_config"].help_text = self.get_pre_fill_config_help_text()

    def clean(self):
        """
        Validate display_fields should have required keys
        "organization", "city", "pacage".

        Only project_url is checked by a model constraint because others
        are not filled by default.
        """
        cleaned_data = super().clean()
        display_dn_fields = cleaned_data.get("display_fields")
        if not all(
            (
                display_dn_fields,
                display_dn_fields.get("city", None),
                display_dn_fields.get("organization", None),
                display_dn_fields.get("pacage", None),
            )
        ):
            self.add_error(
                "display_fields",
                "Les champs city, organization et pacage sont obligatoires.",
            )

        return cleaned_data

    def get_pre_fill_config_help_text(self):
        context = {
            "sources": DemarcheConfig.get_demarche_numerique_value_sources(),
        }
        return render_to_string(
            "admin/moulinette/confighaie/demarche_numerique_pre_fill_config_help_text.html",
            context,
        )


@admin.register(DemarcheConfig)
class DemarcheNumeriqueConfigAdmin(admin.ModelAdmin):
    form = DemarcheNumeriqueAdminForm
    list_display = ["demarche_numerique_number", "display_name"]
