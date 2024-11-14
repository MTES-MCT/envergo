from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.hedges.models import HedgeData
from envergo.moulinette.forms.fields import (
    DisplayCharField,
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
            <span class="help-sidebar-label">
                Nouveaux impacts
                <button type="button"
                        class="fr-btn fr-btn--tertiary-no-outline fr-icon-question-line help-sidebar-button"
                        aria-controls="sidebar-created-surface">
                    Voir l'aide pour le champ « Nouveaux impacts ».
                </button>
            </span>
            """
        ),
        required=True,
        min_value=0,
        max_value=10000000,
        help_text="Surface au sol nouvellement impactée par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        display_unit="m²",
        display_label="Surface nouvellement impactée par le projet :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins — temporaires et définitifs",
        error_messages={
            "max_value": "La valeur saisie est trop élevée. Veuillez saisir un nombre inférieur à 10 000 000.",
        },
    )
    existing_surface = DisplayIntegerField(
        label=_("Existing surface before the project"),
        required=False,
        min_value=0,
        max_value=10000000,
        help_text="Construction, voirie, espaces verts, remblais et bassins",
        widget=forms.HiddenInput,
        display_unit="m²",
        display_label="Surface déjà impactée avant le projet :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins",
        error_messages={
            "max_value": "La valeur saisie est trop élevée. Veuillez saisir un nombre inférieur à 10 000 000.",
        },
    )
    final_surface = DisplayIntegerField(
        label=mark_safe(
            """
            <span class="help-sidebar-label">
                État final
                <button type="button"
                        class="fr-btn fr-btn--tertiary-no-outline fr-icon-question-line help-sidebar-button"
                        aria-controls="sidebar-final-surface">
                    Voir l'aide pour le champ « État final ».
                </button>
            </span>
            """
        ),
        required=False,
        min_value=0,
        max_value=10000000,
        help_text="Surface au sol impactée totale, en comptant l'existant",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        display_unit="m²",
        display_label="Surface impactée totale, y compris l'existant :",
        display_help_text="Bâti, voirie, espaces verts, remblais et bassins — temporaires et définitifs",
        error_messages={
            "max_value": "La valeur saisie est trop élevée. Veuillez saisir un nombre inférieur à 10 000 000.",
        },
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


class HedgeDataChoiceField(forms.ModelChoiceField):
    """A custom model choice field for HedgeData objects."""

    def __init__(self, *args, **kwargs):

        kwargs["widget"] = forms.HiddenInput
        kwargs["queryset"] = HedgeData.objects.all()
        super().__init__(*args, **kwargs)

    def get_display_value(self, value):
        data = self.clean(value)
        display_value = f"{data.length_to_remove()} m / {data.length_to_plant()} m"
        return display_value


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
        label="Quelle est la raison de la destruction de la haie ?",
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
    haies = HedgeDataChoiceField(
        label="Linéaire de haies à détruire / planter",
        required=True,
        error_messages={
            "required": "Localisez précisément les haies concernées par les travaux en ouvrant le module de saisie."
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        submitted_params = set(self.data.keys())
        triage_fields = set(TriageFormHaie.base_fields.keys())

        # Check if only the Triage form fields are submitted
        if submitted_params.issubset(triage_fields):
            self.is_bound = False

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

    def clean_haies(self):
        haies = self.cleaned_data["haies"]
        if haies.length_to_remove() == 0:
            self.add_error(
                "haies",
                "Vous devez indiquer les haies à arracher.",
            )
        return haies


class TriageFormHaie(forms.Form):
    department = DisplayCharField(
        label="Département",
        required=True,
        get_display_value=lambda x: dict(DEPARTMENT_CHOICES).get(x, "Inconnu"),
    )
    element = DisplayChoiceField(
        label="Quel type de végétation est concerné ?",
        widget=forms.RadioSelect,
        choices=(
            ("haie", "Haies ou alignements d’arbres"),
            ("bosquet", "Bosquets"),
            (
                "autre",
                "Autre",
            ),
        ),
        required=True,
        display_label="Type de végétation :",
    )

    travaux = DisplayChoiceField(
        label="Quels sont les travaux envisagés ?",
        widget=forms.RadioSelect,
        choices=(
            (
                "destruction",
                mark_safe(
                    """Destruction<br />
                    <span class="fr-hint-text">
                        Intervention qui supprime définitivement la végétation : arrachage
                        ou coupe à blanc sur une espèce qui ne recèpe pas (ex : chêne,
                        sorbier, noyer, merisier, bouleau, hêtre, tous les résineux…)
                    </span>
                    """
                ),
            ),
            (
                "entretien",
                mark_safe(
                    """Entretien<br />
                    <span class="fr-hint-text">
                        Intervention qui permet la repousse de la végétation : élagage, taille,
                        coupe à blanc sur une espèce capable de recéper.
                    </span>
                    """
                ),
            ),
            (
                "autre",
                "Autre",
            ),
        ),
        required=True,
        display_label="Travaux envisagés :",
    )
