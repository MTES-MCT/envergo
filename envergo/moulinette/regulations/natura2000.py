from functools import cached_property

from django import forms
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation


class ZoneHumide44(MoulinetteCriterion):
    slug = "n2000_zh"
    choice_label = "Natura 2000 > 44 - Zone humide"
    title = "Impact sur zone humide Natura 2000"
    subtitle = "Seuil de déclaration : 100 m²"
    header = "« Liste locale 2 » de Loire-Atlantique (item n°10 de <a href='/static/pdfs/arrete_08042014.pdf' target='_blank' rel='noopener'>l'arrêté préfectoral du 8 avril 2014</a>)"  # noqa

    def get_catalog_data(self):
        data = {}
        data["wetlands_within_25m"] = bool(self.catalog["wetlands_25"])
        data["wetlands_within_100m"] = bool(self.catalog["wetlands_100"])
        data["within_potential_wetlands"] = bool(self.catalog["potential_wetlands"])
        return data

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["within_potential_wetlands"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= 100:
            project_size = "big"
        else:
            project_size = "small"

        return wetland_status, project_size

    @property
    def result_code(self):
        """Return the unique result code"""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
            ("inside", "big"): "inside_big",
            ("inside", "small"): "inside_small",
            ("close_to", "big"): "close_to_big",
            ("close_to", "small"): "close_to_small",
            ("inside_potential", "big"): "inside_potential_big",
            ("inside_potential", "small"): "inside_potential_small",
            ("outside", "big"): "outside",
            ("outside", "small"): "outside",
        }
        code = code_matrix[(wetland_status, project_size)]
        return code

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "inside_big": RESULTS.soumis,
            "inside_small": RESULTS.non_soumis,
            "close_to_big": RESULTS.action_requise,
            "close_to_small": RESULTS.non_soumis,
            "inside_potential_big": RESULTS.action_requise,
            "inside_potential_small": RESULTS.non_soumis,
            "outside": RESULTS.non_soumis,
        }
        result = result_matrix[code]
        return result


class ZoneInondable44(MoulinetteCriterion):
    slug = "n2000_zi"
    choice_label = "Natura 2000 > 44 - Zone inondable"
    title = "Impact sur zone inondable Natura 2000"
    subtitle = "Seuil de déclaration : 200 m²"
    header = "« Liste locale 2 » de Loire-Atlantique (item n°13 de <a href='/static/pdfs/arrete_08042014.pdf' target='_blank' rel='noopener'>l'arrêté préfectoral du 8 avril 2014</a>)"  # noqa

    def get_catalog_data(self):
        data = {}
        data["flood_zones_within_12m"] = bool(self.catalog["flood_zones_12"])
        return data

    @cached_property
    def result_code(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        else:
            flood_zone_status = "outside"

        if self.catalog["created_surface"] >= 200:
            project_size = "big"
        else:
            project_size = "small"

        result_matrix = {
            "inside": {
                "big": RESULTS.soumis,
                "small": RESULTS.non_soumis,
            },
            "outside": {
                "big": RESULTS.non_applicable,
                "small": RESULTS.non_applicable,
            },
        }

        result = result_matrix[flood_zone_status][project_size]
        return result


class IOTA(MoulinetteCriterion):
    slug = "n2000_iota"
    choice_label = "Natura 2000 > IOTA"
    title = "Projet soumis à la Loi sur l'eau"
    header = "« Liste nationale » Natura 2000 (item n°4 de l'<a href='https://www.legifrance.gouv.fr/codes/id/LEGISCTA000022090322/' target='_blank' rel='noopener'>article R414-19 du Code de l'Environnement</a>)"

    @cached_property
    def result_code(self):
        return self.moulinette.loi_sur_leau.result


class LotissementForm(forms.Form):

    # I sacrificed a frog to the god of bad translations for the right to use
    # this variable name. Sorry.
    is_lotissement = forms.ChoiceField(
        label=_("Le projet concerne-t-il un lotissement ?"),
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


class Lotissement44(MoulinetteCriterion):
    slug = "n2000_lotissement"
    choice_label = "Natura 2000 > 44 - Lotissement"
    title = "Lotissement dans zone Natura 2000"
    header = "« Liste locale 1 » de Loire-Atlantique (au 1° de l'article 2 de l'<a href='/static/pdfs/arrete_16062011.pdf' target='_blank' rel='noopener'>arrêté préfectoral du 16 juin 2011</a>)"
    form_class = LotissementForm

    @cached_property
    def result_code(self):

        form = self.get_form()
        if form.is_valid():
            is_lotissement = form.cleaned_data["is_lotissement"] == "oui"
            return "soumis" if is_lotissement else "non_soumis"

        return "non_disponible"


class Natura2000(MoulinetteRegulation):
    slug = "natura2000"
    title = "Natura 2000"
    criterion_classes = [ZoneHumide44, ZoneInondable44, IOTA, Lotissement44]
