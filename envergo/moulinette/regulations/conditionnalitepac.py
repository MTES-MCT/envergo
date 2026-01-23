import logging
from decimal import Decimal as D

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import MinLengthPacCondition, PlantationConditionMixin
from envergo.moulinette.forms import DisplayIntegerField
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator

logger = logging.getLogger(__name__)


class Bcae8Regulation(HaieRegulationEvaluator):
    choice_label = "Haie > Conditionnalité PAC"

    PROCEDURE_TYPE_MATRIX = {
        "interdit": "interdit",
        "soumis": "declaration",
        "dispense": "declaration",
        "non_soumis": "declaration",
    }


def keep_fields(fields, keys):
    """Only keep selected fields from the field list.

    This is a tiny helper to make the code more readable.
    """
    return {k: v for k, v in fields.items() if k in keys}


class Bcae8Form(forms.Form):
    lineaire_total = DisplayIntegerField(
        label="Linéaire total de haies sur l’exploitation déclarée à la PAC (en m) :",
        help_text="Si la valeur exacte est inconnue, une estimation est suffisante",
        required=True,
        min_value=0,
        widget=forms.TextInput(
            attrs={"placeholder": "En mètres", "inputmode": "numeric"}
        ),
        display_unit="m",
        display_help_text="",
        display_label="Linéaire total de haies sur l’exploitation déclarée à la PAC :",
    )

    transfert_parcelles = forms.ChoiceField(
        label="Le projet est-il réalisé à l'occasion d'un transfert de parcelles ?",
        help_text="""
        Transfert dans le cas d’un agrandissement d’exploitation, de l'installation
        d’un nouvel exploitant, d'échange de parcelles…""",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    batiment_exploitation = forms.ChoiceField(
        label="""
        La destruction a-t-elle lieu dans le cadre de la construction ou l’agrandissement d’un bâtiment d’exploitation
        autorisé par un permis de construire ?""",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    amenagement_dup = forms.ChoiceField(
        label="""
        La destruction a-t-elle lieu à l’occasion d’une opération d’aménagement foncier déclarée d’utilité
        publique et ayant fait l’objet d’une consultation du public ?""",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    meilleur_emplacement = forms.ChoiceField(
        label="""
        Le projet dispose-t-il d’une attestation de meilleur emplacement environnemental,
        délivrée par un organisme agréé ?""",
        help_text=f"""
        La liste des organismes habilités à délivrer un conseil environnemental est
        <a title="Liste des organismes habilités - ouvre une nouvelle fenêtre" target="_blank" rel="noopener external"
        href="{settings.HAIE_FAQ_URLS["BEST_ENVIRONMENTAL_LOCATION_ORGANIZATIONS_LIST"]}">
        disponible ici</a>.""",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    motif_pac = forms.ChoiceField(
        label="Le projet est-il réalisé pour l’un de ces motifs prévus par les règles de conditionnalité PAC ?",
        widget=forms.RadioSelect,
        choices=(
            (
                "protection_incendie",
                "Décision du préfet pour protection contre l'incendie",
            ),
            (
                "gestion_sanitaire",
                "Décision du préfet pour gestion sanitaire de la haie (éradication d’une maladie)",
            ),
            (
                "rehabilitation_fosse",
                "Réhabiliter un fossé pour rétablir une circulation hydraulique",
            ),
            ("aucun", "Aucun de ces cas"),
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial
        localisation_pac = data.get("localisation_pac")
        if localisation_pac == "non":
            # We know the result will be "non soumis"
            self.fields = {}
            return

        motif = data.get("motif")
        if motif == "amelioration_culture":
            self.fields = keep_fields(
                self.fields,
                ("lineaire_total", "meilleur_emplacement", "transfert_parcelles"),
            )
        elif motif == "amenagement":
            self.fields = keep_fields(
                self.fields,
                ("lineaire_total", "batiment_exploitation", "amenagement_dup"),
            )
        elif motif == "amelioration_ecologique":
            self.fields = keep_fields(
                self.fields,
                ("lineaire_total", "meilleur_emplacement", "motif_pac"),
            )
        elif motif in ("securite", "amelioration_ecologique", "autre"):
            self.fields = keep_fields(
                self.fields,
                ("lineaire_total", "motif_pac"),
            )
        else:
            self.fields = keep_fields(
                self.fields,
                ("lineaire_total",),
            )

    def clean_lineaire_total(self):
        lineaire_total = self.cleaned_data["lineaire_total"]
        if lineaire_total <= 0:
            raise forms.ValidationError("La valeur doit être positive.")
        return lineaire_total

    def clean(self):
        data = super().clean()
        meilleur_emplacement = data.get("meilleur_emplacement")
        reimplantation = self.data.get("reimplantation")

        if meilleur_emplacement == "oui" and reimplantation == "remplacement":
            self.add_error(
                "meilleur_emplacement",
                ValidationError(
                    """Le remplacement de la haie au même endroit est incompatible avec le
                    meilleur emplacement environnemental. Veuillez modifier l'une ou l'autre
                    des réponses du formulaire.""",
                    code="inconsistent_reimplantation",
                ),
            )
        elif meilleur_emplacement == "oui" and reimplantation == "non":
            self.add_error(
                "meilleur_emplacement",
                ValidationError(
                    """L’absence de réimplantation de la haie est incompatible avec le
                    meilleur emplacement environnemental. Veuillez modifier l'une ou l'autre
                    des réponses du formulaire.""",
                    code="inconsistent_reimplantation",
                ),
            )


class Bcae8(PlantationConditionMixin, CriterionEvaluator):
    choice_label = "Conditionnalité PAC > BCAE8"
    slug = "bcae8"
    form_class = Bcae8Form
    plantation_conditions = [MinLengthPacCondition]

    RESULT_MATRIX = {
        "non_soumis": RESULTS.non_soumis,
        "dispense_petit": RESULTS.dispense,
        "soumis_remplacement": RESULTS.soumis,
        "soumis_transfert_parcelles": RESULTS.soumis,
        "soumis_meilleur_emplacement": RESULTS.soumis,
        "soumis_chemin_acces": RESULTS.soumis,
        "soumis_amenagement": RESULTS.soumis,
        "soumis_fosse": RESULTS.soumis,
        "soumis_incendie": RESULTS.soumis,
        "soumis_maladie": RESULTS.soumis,
        "interdit_transfert_parcelles": RESULTS.interdit,
        "interdit_amelioration_culture": RESULTS.interdit,
        "interdit_amelioration_ecologique": RESULTS.interdit,
        "interdit_chemin_acces": RESULTS.interdit,
        "interdit_amenagement": RESULTS.interdit,
        "interdit_embellissement": RESULTS.interdit,
        "interdit_securite": RESULTS.interdit,
        "interdit_autre": RESULTS.interdit,
    }

    # Result code to replantation coefficient
    R_MATRIX = {
        "non_soumis": D("0"),
        "dispense_petit": D("1"),
        "soumis_remplacement": D("1"),
        "soumis_transfert_parcelles": D("1"),
        "soumis_meilleur_emplacement": D("1"),
        "soumis_chemin_acces": D("0"),
        "soumis_amenagement": D("0"),
        "soumis_fosse": D("0"),
        "soumis_incendie": D("0"),
        "soumis_maladie": D("0"),
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        catalog["authorized_organizations_list_url"] = settings.HAIE_FAQ_URLS[
            "BEST_ENVIRONMENTAL_LOCATION_ORGANIZATIONS_LIST"
        ]
        is_lte_2percent_pac = False
        haies = self.catalog.get("haies")
        if haies:
            catalog["lineaire_detruit_pac"] = haies.lineaire_detruit_pac()
            catalog["lineaire_type_4_sur_parcelle_pac"] = (
                haies.lineaire_type_4_sur_parcelle_pac()
            )

            lineaire_detruit_pac = haies.lineaire_detruit_pac()
            if "lineaire_total" in catalog:
                lineaire_total = catalog["lineaire_total"]
                ratio_detruit = lineaire_detruit_pac / lineaire_total
                is_lte_2percent_pac = ratio_detruit <= 0.02 or lineaire_detruit_pac <= 5

        catalog["is_lte_2percent_pac"] = is_lte_2percent_pac
        return catalog

    def get_result_data(self):

        haies = self.catalog["haies"]
        lineaire_detruit_pac = haies.lineaire_detruit_pac()
        lte_10m_sections_only = all(
            section.length <= 10 for section in haies.hedges_to_remove_pac()
        )

        return (
            # Main vars
            self.catalog["motif"],
            self.catalog["reimplantation"],
            self.catalog["localisation_pac"],
            # Additional vars
            self.catalog.get("transfert_parcelles"),
            self.catalog.get("batiment_exploitation"),
            self.catalog.get("amenagement_dup"),
            self.catalog.get("meilleur_emplacement"),
            self.catalog.get("motif_pac"),
            # Computed vars
            lineaire_detruit_pac,
            self.catalog["is_lte_2percent_pac"],
            lte_10m_sections_only,
        )

    def get_result_motif_pac(self, motif_pac):
        if motif_pac == "protection_incendie":
            return "soumis_incendie"
        elif motif_pac == "gestion_sanitaire":
            return "soumis_maladie"
        elif motif_pac == "rehabilitation_fosse":
            return "soumis_fosse"
        else:
            raise ValueError("Unhandled motif_pac value: %s" % motif_pac)

    def get_result_code(self, result_data):
        """Override the default method to avoid an oversize (and hard to debug) matrix."""
        (
            motif,
            reimplantation,
            localisation_pac,
            transfert_parcelles,
            batiment_exploitation,
            amenagement_dup,
            meilleur_emplacement,
            motif_pac,
            lineaire_detruit_pac,
            is_lte_2percent_pac,
            lte_10m_sections_only,
        ) = result_data

        result_code = None

        if localisation_pac == "non" or lineaire_detruit_pac == 0:
            result_code = "non_soumis"
        else:
            if is_lte_2percent_pac:
                if reimplantation == "remplacement":
                    if motif == "chemin_acces":
                        # X
                        pass
                    else:
                        result_code = "dispense_petit"
                elif reimplantation == "replantation":
                    result_code = "dispense_petit"
                elif reimplantation == "non":
                    if motif == "amelioration_culture":
                        result_code = "interdit_transfert_parcelles"
                    elif motif == "chemin_acces":
                        if lte_10m_sections_only:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui" or batiment_exploitation == "oui":
                            result_code = "soumis_amenagement"
                        else:
                            result_code = "interdit_amenagement"
                    elif motif == "amelioration_ecologique":
                        # X
                        pass
                    elif motif == "embellissement":
                        result_code = "interdit_embellissement"
                    elif motif == "autre":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_autre"

            elif not is_lte_2percent_pac:
                if reimplantation == "remplacement":
                    if motif == "chemin_acces":
                        # X
                        pass
                    else:
                        result_code = "soumis_remplacement"
                elif reimplantation == "replantation":
                    if motif == "amelioration_culture":
                        if transfert_parcelles == "oui":
                            result_code = "soumis_transfert_parcelles"
                        elif meilleur_emplacement == "oui":
                            result_code = "soumis_meilleur_emplacement"
                        else:
                            result_code = "interdit_amelioration_culture"
                    elif motif == "chemin_acces":
                        if lte_10m_sections_only:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui" or batiment_exploitation == "oui":
                            result_code = "soumis_amenagement"
                        else:
                            result_code = "interdit_amenagement"
                    elif motif == "amelioration_ecologique":
                        if meilleur_emplacement == "oui":
                            result_code = "soumis_meilleur_emplacement"
                        else:
                            result_code = "interdit_amelioration_ecologique"
                    elif motif == "embellissement":
                        result_code = "interdit_embellissement"
                    elif motif == "autre":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_autre"
                elif reimplantation == "non":
                    if motif == "amelioration_culture":
                        result_code = "interdit_transfert_parcelles"
                    elif motif == "chemin_acces":
                        if lte_10m_sections_only:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui" or batiment_exploitation == "oui":
                            result_code = "soumis_amenagement"
                        else:
                            result_code = "interdit_amenagement"
                    elif motif == "amelioration_ecologique":
                        # X
                        pass
                    elif motif == "embellissement":
                        result_code = "interdit_embellissement"
                    elif motif == "autre":
                        if motif_pac != "aucun":
                            result_code = self.get_result_motif_pac(motif_pac)
                        else:
                            result_code = "interdit_autre"

        # This case should not happen, but better be safe
        if result_code is None:
            logger.error("No result code found for %s", result_data)
            result_code = RESULTS.non_disponible

        return result_code

    def get_replantation_coefficient(self):
        R = self.R_MATRIX.get(self._result_code, D("1"))
        haies = self.catalog["haies"]
        minimum_length_to_plant = D(haies.lineaire_detruit_pac()) * R
        if haies.length_to_remove() > 0:
            R = minimum_length_to_plant / D(haies.length_to_remove())
        return round(R, 2)
