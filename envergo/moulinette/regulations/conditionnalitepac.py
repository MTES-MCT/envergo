import logging

from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms import DisplayIntegerField
from envergo.moulinette.regulations import CriterionEvaluator

logger = logging.getLogger(__name__)


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
        widget=forms.TextInput(attrs={"placeholder": "En mètres"}),
        display_unit="m",
        display_help_text="",
        display_label="Linéaire total de haies sur l’exploitation déclarée à la PAC :",
    )

    transfert_parcelles = forms.ChoiceField(
        label="Le projet est-il réalisé à l'occasion d'un transfert de parcelles ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    amenagement_dup = forms.ChoiceField(
        label="L’aménagement a-t-il été déclaré d’utilité publique et fait l’objet d’une consultation du public ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    meilleur_emplacement = forms.ChoiceField(
        label="""
        Le projet est-il accompagné par un organisme agréé, en mesure de délivrer une
        attestation de meilleur emplacement environnemental ?""",
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
        localisation_pac = self.data.get("localisation_pac")
        if localisation_pac == "non":
            # We know the result will be "non soumis"
            self.fields = {}
            return

        motif = self.data.get("motif")
        if motif == "amelioration_culture":
            self.fields = keep_fields(
                self.fields, ("lineaire_total", "transfert_parcelles")
            )
        elif motif == "amenagement":
            self.fields = keep_fields(
                self.fields, ("lineaire_total", "amenagement_dup")
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
                """Le remplacement de la haie au même endroit est incompatible avec le
                meilleur emplacement environnemental. Veuillez modifier l'une ou l'autre
                des réponses du formulaire.""",
            )
        elif meilleur_emplacement == "oui" and reimplantation == "non":
            self.add_error(
                "meilleur_emplacement",
                """L’absence de réimplantation de la haie est incompatible avec le
                meilleur emplacement environnemental. Veuillez modifier l'une ou l'autre
                des réponses du formulaire.""",
            )


class Bcae8(CriterionEvaluator):
    choice_label = "Conditionnalité PAC > BCAE8"
    slug = "bcae8"
    form_class = Bcae8Form

    RESULT_MATRIX = {
        "non_soumis": RESULTS.non_soumis,
        "dispense_petit": RESULTS.non_soumis,
        "soumis_remplacement": RESULTS.soumis,
        "soumis_transfert_parcelles": RESULTS.soumis,
        "soumis_meilleur_emplacement": RESULTS.soumis,
        "soumis_chemin_acces": RESULTS.soumis,
        "soumis_amenagement": RESULTS.soumis,
        "soumis_autre": RESULTS.soumis,
        "interdit_transfert_parcelles": RESULTS.interdit,
        "interdit_amelioration_culture": RESULTS.interdit,
        "interdit_amelioration_ecologique": RESULTS.interdit,
        "interdit_meilleur_emplacement": RESULTS.interdit,
        "interdit_chemin_acces": RESULTS.interdit,
        "interdit_amenagement": RESULTS.interdit,
        "interdit_embellissement": RESULTS.interdit,
        "interdit_securite": RESULTS.interdit,
        "interdit_autre": RESULTS.interdit,
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["lineaire_detruit_pac"] = haies.lineaire_detruit_pac()
            catalog["lineaire_type_4_sur_parcelle_pac"] = (
                haies.lineaire_type_4_sur_parcelle_pac()
            )

        return catalog

    def get_result_data(self):
        is_small = False
        haies = self.catalog["haies"]
        lineaire_detruit_pac = haies.lineaire_detruit_pac()
        ratio_detruit = 0
        if "lineaire_total" in self.catalog:
            lineaire_total = self.catalog["lineaire_total"]
            ratio_detruit = lineaire_detruit_pac / lineaire_total
            is_small = ratio_detruit <= 0.02 or lineaire_detruit_pac <= 5

        return (
            # Main vars
            self.catalog["motif"],
            self.catalog["reimplantation"],
            self.catalog["localisation_pac"],
            # Additional vars
            self.catalog.get("transfert_parcelles"),
            self.catalog.get("amenagement_dup"),
            self.catalog.get("meilleur_emplacement"),
            self.catalog.get("motif_pac"),
            # Computed vars
            lineaire_detruit_pac,
            is_small,
        )

    def get_result_code(self, result_data):
        """Override the default method to avoid an oversize (and hard to debug) matrix."""
        (
            motif,
            reimplantation,
            localisation_pac,
            transfert_parcelles,
            amenagement_dup,
            meilleur_emplacement,
            motif_pac,
            lineaire_detruit_pac,
            is_small,
        ) = result_data

        result_code = None

        if localisation_pac == "non" or lineaire_detruit_pac == 0:
            result_code = "non_soumis"
        else:
            if is_small:
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
                        if transfert_parcelles == "oui":
                            result_code = "interdit_transfert_parcelles"
                        else:
                            result_code = "interdit_amelioration_culture"
                    elif motif == "chemin_acces":
                        if lineaire_detruit_pac <= 10:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui":
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
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_autre"

            elif not is_small:
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
                        else:
                            result_code = "interdit_amelioration_culture"
                    elif motif == "chemin_acces":
                        if lineaire_detruit_pac <= 10:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui":
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
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_autre"
                elif reimplantation == "non":
                    if motif == "amelioration_culture":
                        if transfert_parcelles == "oui":
                            result_code = "interdit_transfert_parcelles"
                        else:
                            result_code = "interdit_amelioration_culture"
                    elif motif == "chemin_acces":
                        if lineaire_detruit_pac <= 10:
                            result_code = "soumis_chemin_acces"
                        else:
                            result_code = "interdit_chemin_acces"
                    elif motif == "securite":
                        if motif_pac != "aucun":
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_securite"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui":
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
                            result_code = "soumis_autre"
                        else:
                            result_code = "interdit_autre"

        # This case should not happen, but better be safe
        if result_code is None:
            logger.error("No result code found for %s", result_data)
            result_code = RESULTS.non_disponible

        return result_code
