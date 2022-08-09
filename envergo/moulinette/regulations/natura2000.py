from functools import cached_property

from django import forms
from django.contrib.gis.db.models import MultiPolygonField, Union
from django.db.models import F
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation


class N2000100m2(MoulinetteCriterion):
    slug = "n2000_zh_100m2"
    title = "Impact sur zone humide Natura 2000"
    subtitle = "Seuil de déclaration : 100m²"
    header = "Rubrique 3.3.1.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

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
            ("inside", "big"): "soumis",
            ("inside", "small"): "non_soumis",
            ("close_to", "big"): "action_requise_close_to",
            ("close_to", "small"): "non_soumis",
            ("inside_potential", "big"): "action_requise_inside_potential",
            ("inside_potential", "small"): "non_soumis",
            ("outside", "big"): "non_soumis",
            ("outside", "small"): "non_soumis",
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
            "soumis": RESULTS.soumis,
            "non_soumis": RESULTS.non_soumis,
            "non_applicable": RESULTS.non_applicable,
            "action_requise_close_to": RESULTS.action_requise,
            "action_requise_inside_potential": RESULTS.action_requise,
        }
        result = result_matrix[code]
        return result


class N2000ZI200m2(MoulinetteCriterion):
    slug = "n2000_zi_200m2"
    title = "Impact sur zone inondable Natura 2000"
    subtitle = "Seuil de déclaration : 200m²"
    header = "Rubrique 3.3.1.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    def get_catalog_data(self):
        data = {}
        data["flood_zones_within_12m"] = bool(self.catalog["flood_zones_12"])
        return data

    @cached_property
    def result(self):
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
                "small": RESULTS.non_soumis,
            },
        }

        result = result_matrix[flood_zone_status][project_size]
        return result


class N2000IOTA(MoulinetteCriterion):
    slug = "n2000_iota"
    title = "Projet soumis à la Loi sur l'eau"
    subtitle = "Je suis un sous-titre"
    header = "Bla bla bla"

    @cached_property
    def result(self):
        return self.moulinette.loi_sur_leau.result


class LotissementForm(forms.Form):

    # I sacrificed a frog to the god of bad translations for the right to use
    # this variable name. Sorry.
    is_lotissement = forms.ChoiceField(
        label=_('Le projet concerne-t-il un lotissement ?'),
        widget=forms.RadioSelect,
        choices=(('oui', 'Oui'), ('non', 'Non')),
        required=True)


class N2000Lotissement(MoulinetteCriterion):
    slug = "n2000_lotissement"
    title = "Lotissement dans zone Natura 2000"
    subtitle = "Je suis un sous-titre"
    header = "Bla bla bla"
    form_class = LotissementForm

    @cached_property
    def result(self):

        form = self.form_class(self.moulinette.raw_data)
        if form.is_valid():
            is_lotissement = form.cleaned_data['is_lotissement'] == 'oui'
            return 'soumis' if is_lotissement else 'non_soumis'

        return "non_disponible"



class Natura2000(MoulinetteRegulation):
    slug = "natura2000"
    title = "Natura 2000"
    criterion_classes = [N2000100m2, N2000ZI200m2, N2000IOTA, N2000Lotissement]
