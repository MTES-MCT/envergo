from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms import DisplayIntegerField
from envergo.moulinette.regulations import CriterionEvaluator


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

    CODES = [
        "non_soumis",
        "non_soumis_petit",
        "soumis_remplacement",
        "soumis_transfert_parcelles",
        "soumis_meilleur_emplacement",
        "soumis_chemin_acces",
        "soumis_amenagement",
        "soumis_autre",
        "interdit_transfert_parcelles",
        "interdit_meilleur_emplacement",
        "interdit_chemin_acces",
        "interdit_amenagement",
        "interdit_autre",
    ]

    RESULT_MATRIX = {
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_petit": RESULTS.non_soumis,
        "soumis_remplacement": RESULTS.soumis,
        "soumis_transfert_parcelles": RESULTS.soumis,
        "soumis_meilleur_emplacement": RESULTS.soumis,
        "soumis_chemin_acces": RESULTS.soumis,
        "soumis_amenagement": RESULTS.soumis,
        "soumis_autre": RESULTS.soumis,
        "interdit_transfert_parcelles": RESULTS.interdit,
        "interdit_meilleur_emplacement": RESULTS.interdit,
        "interdit_chemin_acces": RESULTS.interdit,
        "interdit_amenagement": RESULTS.interdit,
        "interdit_autre": RESULTS.interdit,
    }

    def get_result_data(self):
        is_petit = False
        lineaire_detruit = self.catalog["haies"].length_to_remove()
        if "lineaire_total" in self.catalog:
            is_petit = (
                lineaire_detruit <= 5
                or lineaire_detruit <= 0.02 * self.catalog["lineaire_total"]
            )

        return (
            self.catalog["profil"],
            self.catalog["motif"],
            self.catalog["reimplantation"],
            is_petit,
            lineaire_detruit,
            self.catalog.get("amenagement_dup"),
            self.catalog.get("motif_qc"),
        )

    def get_result_code(self, result_data):
        """Override the default method to avoid an oversize (and hard to debug) matrix."""
        (
            profil,
            motif,
            reimplantation,
            is_petit,
            lineaire_detruit,
            amenagement_dup,
            motif_qc,
        ) = result_data

        if profil == "agri_pac":
            if reimplantation == "remplacement":
                if is_petit:
                    result_code = "non_soumis_petit"
                else:
                    result_code = "soumis_remplacement"
            elif reimplantation == "compensation":
                if is_petit:
                    result_code = "non_soumis_petit"
                else:
                    if motif == "transfert_parcelles":
                        result_code = "soumis_transfert_parcelles"
                    elif motif == "meilleur_emplacement":
                        result_code = "soumis_meilleur_emplacement"
                    elif motif == "chemin_acces":
                        if lineaire_detruit <= 10:
                            result_code = "soumis_chemin_acces"
                        else:  # lineaire_detruit > 10
                            result_code = "interdit_chemin_acces"
                    elif motif == "amenagement":
                        if amenagement_dup == "oui":
                            result_code = "soumis_amenagement"
                        else:  # amenagement_dup=non
                            result_code = "interdit_amenagement"
                    else:  # motif=autre
                        if motif_qc == "aucun":
                            result_code = "interdit_autre"
                        else:  # motif_qc=protection_incendie, gestion_sanitaire, rehabilitation_fosse
                            result_code = "soumis_autre"
            else:  # reimplantation=non
                if motif == "chemin_acces":
                    if lineaire_detruit <= 10:
                        result_code = "soumis_chemin_acces"
                    else:  # lineaire_detruit > 10
                        result_code = "interdit_chemin_acces"
                elif motif == "autre":
                    if motif_qc == "aucun":
                        result_code = "interdit_autre"
                    else:  # motif_qc=protection_incendie, gestion_sanitaire, rehabilitation_fosse
                        result_code = "soumis_autre"
                elif motif == "amenagement":
                    if amenagement_dup == "oui":
                        result_code = "soumis_amenagement"
                    else:  # amenagement_dup=non
                        result_code = "interdit_amenagement"
                else:  # motif=transfert_parcelles
                    result_code = "interdit_transfert_parcelles"
        else:
            # SI profil=autre → non_soumis
            result_code = "non_soumis"

        return result_code
