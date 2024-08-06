from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator


class MaintienHaiesForm(forms.Form):
    lineaire_detruit = forms.IntegerField(
        label="Linéaire de haie détruit (en m) :",
        required=False,
        min_value=0,
        widget=forms.TextInput(attrs={"placeholder": "En mètres"}),
    )

    lineaire_total = forms.IntegerField(
        label="Linéaire total de haie sur l’exploitation (en m) :",
        required=False,
        min_value=0,
        widget=forms.TextInput(attrs={"placeholder": "En mètres"}),
    )

    amenagement_dup = forms.ChoiceField(
        label="L’aménagement a-t-il été déclaré d’utilité publique et fait l’objet d’une consultation du public ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=False,
    )

    motif_qc = forms.ChoiceField(
        label="Quelle est la raison de l’arrachage de la haie ?",
        widget=forms.RadioSelect,
        choices=(
            (
                "protection_incendie",
                "Décision du préfet pour protection contre l'incendie",
            ),
            (
                "gestion_sanitaire",
                "Décision du préfet pour gestion sanitaire de la haie",
            ),
            (
                "rehabilitation_fosse",
                "Réhabiliter un fossé pour rétablir une circulation hydraulique",
            ),
            ("aucun", "Aucun de ces cas"),
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profil = self.data.get("profil")
        if profil == "agri_pac":
            self.fields["lineaire_detruit"].required = True
            self.fields["lineaire_total"].required = True
            motif = self.data.get("motif")
            if motif == "amenagement":
                self.fields["amenagement_dup"].required = True
            if motif == "autre":
                self.fields["motif_qc"].required = True


class MaintienHaies(CriterionEvaluator):
    choice_label = "BCAE8 > Maintien des haies"
    slug = "maintien_haies"
    form_class = MaintienHaiesForm

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
        if self.catalog["lineaire_detruit"] and self.catalog["lineaire_total"]:
            is_petit = (
                self.catalog["lineaire_detruit"] < 5
                or self.catalog["lineaire_detruit"]
                <= 0.02 * self.catalog["lineaire_total"]
            )

        return (
            self.catalog["profil"],
            self.catalog["motif"],
            self.catalog["reimplantation"],
            is_petit,
            self.catalog["lineaire_detruit"],
            self.catalog["amenagement_dup"],
            self.catalog["motif_qc"],
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
