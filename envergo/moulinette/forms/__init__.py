from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.moulinette.forms.fields import (
    DisplayChoiceField,
    DisplayIntegerField,
    extract_choices,
    extract_display_function,
)


class BaseMoulinetteForm(forms.Form):
    pass


class MoulinetteFormAmenagement(BaseMoulinetteForm):
    created_surface = DisplayIntegerField(
        label=mark_safe(
            """
            Nouveaux impacts
            <button type="button"
                    id="sidebar-button"
                    aria-controls="help-sidebar">
                help
            </button>
            """
        ),
        required=True,
        min_value=0,
        help_text="Surface au sol nouvellement impactée par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        display_unit="m²",
        display_label="Surface nouvellement impactée par le projet :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins — temporaires et définitifs",
    )
    existing_surface = DisplayIntegerField(
        label=_("Existing surface before the project"),
        required=False,
        min_value=0,
        help_text="Construction, voirie, espaces verts, remblais et bassins",
        widget=forms.HiddenInput,
        display_unit="m²",
        display_label="Surface déjà impactée avant le projet :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins",
    )
    final_surface = DisplayIntegerField(
        label=_("Total surface at the end of the project"),
        required=False,
        min_value=0,
        help_text="Surface au sol impactée totale, en comptant l'existant",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        display_unit="m²",
        display_label="Surface impactée totale, y compris l'existant :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins — temporaires et définitifs",
    )
    address = forms.CharField(
        label=_("Search for the address to center the map"),
        help_text=_("Type in a few characters to see suggestions"),
        required=False,
    )
    lng = forms.DecimalField(
        label=_("Longitude"), required=True, max_digits=9, decimal_places=6
    )
    lat = forms.DecimalField(
        label=_("Latitude"), required=True, max_digits=9, decimal_places=6
    )

    def clean(self):
        data = super().clean()

        if self.errors:
            return data

        created_surface = data.get("created_surface")
        final_surface = data.get("final_surface")

        if final_surface is None:
            self.add_error("final_surface", _("This field is required"))

        # New version, project surface is provided
        # If existing_surface is missing, we compute it
        # If both values are somehow provided, we check that they are consistent
        else:
            if final_surface < created_surface:
                self.add_error(
                    "final_surface",
                    _("The total surface must be greater than the created surface"),
                )
        return data


REIMPLANTATION_CHOICES = (
    (
        "remplacement",
        mark_safe(
            "<span>Oui, en remplaçant la haie détruite <b>au même</b> endroit<span>"
        ),
        "Oui, en remplaçant la haie détruite au même endroit",
    ),
    (
        "compensation",
        mark_safe("<span>Oui, en plantant une haie <b>à un autre</b> endroit<span>"),
        "Oui, en plantant une haie à un autre endroit",
    ),
    ("non", "Non, aucune réimplantation", "Non, aucune réimplantation"),
)


MOTIF_CHOICES = (
    (
        "transfert_parcelles",
        mark_safe(
            "Transfert de parcelles entre exploitations<br />"
            '<span class="fr-hint-text">Agrandissement, échange de parcelles, nouvelle installation…</span>'
        ),
    ),
    (
        "chemin_acces",
        mark_safe(
            "Créer un chemin d’accès<br />"
            '<span class="fr-hint-text">Chemin nécessaire pour l’accès et l’exploitation de la parcelle</span>'
        ),
    ),
    (
        "meilleur_emplacement",
        mark_safe(
            "Replanter la haie à un meilleur emplacement environnemental<br />"
            '<span class="fr-hint-text">Plantation justifiée par un organisme agréé</span>'
        ),
    ),
    (
        "amenagement",
        "Réaliser une opération d’aménagement foncier",
    ),
    (
        "autre",
        "Autre",
    ),
)


class MoulinetteFormHaie(BaseMoulinetteForm):
    profil = forms.ChoiceField(
        label="J’effectue cette demande en tant que :",
        widget=forms.RadioSelect,
        choices=(
            ("agri_pac", "Exploitant-e agricole bénéficiaire de la PAC"),
            (
                "autre",
                mark_safe(
                    "Autre<br />"
                    '<span class="fr-hint-text">'
                    "Collectivité, aménageur, gestionnaire de réseau, particulier, etc."
                    "</span>"
                ),
            ),
        ),
        required=True,
    )
    motif = forms.ChoiceField(
        label="Quelle est la raison de l’arrachage de la haie ?",
        widget=forms.RadioSelect,
        choices=MOTIF_CHOICES,
        required=True,
    )

    reimplantation = DisplayChoiceField(
        label="Est-il prévu de planter une nouvelle haie ?",
        widget=forms.RadioSelect,
        choices=extract_choices(REIMPLANTATION_CHOICES),
        required=True,
        get_display_value=extract_display_function(REIMPLANTATION_CHOICES),
    )

    def clean(self):
        data = super().clean()

        reimplantation = data.get("reimplantation")
        motif = data.get("motif")

        if reimplantation == "remplacement" and motif == "meilleur_emplacement":
            self.add_error(
                "motif",
                "Le remplacement de la haie au même endroit est incompatible avec le meilleur emplacement"
                " environnemental. Veuillez modifier l'une ou l'autre des réponses du formulaire.",
            )
        elif reimplantation == "remplacement" and motif == "chemin_acces":
            self.add_error(
                "motif",
                "Le remplacement de la haie au même endroit est incompatible avec le percement d'un chemin"
                " d'accès. Veuillez modifier l'une ou l'autre des réponses du formulaire.",
            )
        elif reimplantation == "non" and motif == "meilleur_emplacement":
            self.add_error(
                "motif",
                "L’absence de réimplantation de la haie est incompatible avec le meilleur emplacement"
                " environnemental. Veuillez modifier l'une ou l'autre des réponses du formulaire.",
            )

        return data
