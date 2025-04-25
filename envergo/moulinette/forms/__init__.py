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
        widget=forms.TextInput(
            attrs={"placeholder": _("In square meters"), "inputmode": "numeric"}
        ),
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
        widget=forms.TextInput(
            attrs={"placeholder": _("In square meters"), "inputmode": "numeric"}
        ),
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
        "replantation",
        mark_safe("<span>Oui, en plantant une haie <b>à un autre</b> endroit<span>"),
        "Oui, en plantant une haie à un autre endroit",
    ),
    ("non", "Non, aucune réimplantation", "Non, aucune réimplantation"),
)


MOTIF_CHOICES = (
    (
        "amelioration_culture",
        mark_safe(
            """
            Amélioration des conditions d’exploitation agricole<br />
            <span class="fr-hint-text">
                Faciliter l’exploitation mécanique ou la culture des parcelles
            </span>
            """
        ),
    ),
    (
        "chemin_acces",
        mark_safe(
            """
            Création d’un accès à la parcelle<br/>
            <span class="fr-hint-text">
                Brèche dans une haie pour créer un chemin, permettre le passage d’engins…
            </span>
            """
        ),
    ),
    (
        "securite",
        mark_safe(
            """
            Mise en sécurité<br/>
            <span class="fr-hint-text">
                Sécurité des riverains, de la voirie, d’une installation attenante,
                réparation suite à un effondrement…
            </span>
            """
        ),
    ),
    (
        "amenagement",
        mark_safe(
            """
            Opération d’aménagement foncier<br/>
            <span class="fr-hint-text">
                Création ou agrandissement d’un bâtiment, d’un lotissement, d’une infrastructure…
            </span>
            """
        ),
    ),
    (
        "amelioration_ecologique",
        mark_safe(
            """
            Amélioration écologique<br/>
            <span class="fr-hint-text">
                Restauration de la continuité écologique, réimplantation sur un meilleur
                emplacement environnemental…
            </span>
            """
        ),
    ),
    (
        "embellissement",
        mark_safe(
            """
            Embellissement ou agrément<br/>
            <span class="fr-hint-text">
                Amélioration de l’ensoleillement d’une habitation, dégagement d’une vue
                depuis un jardin…
            </span>
            """
        ),
    ),
    (
        "autre",
        "Autre",
    ),
)

LOCALISATION_PAC_CHOICES = (
    ("oui", "Oui, au moins une des haies"),
    ("non", "Non, aucune des haies"),
)


class HedgeDataChoiceField(forms.ModelChoiceField):
    """A custom model choice field for HedgeData objects."""

    def __init__(self, *args, **kwargs):

        kwargs["widget"] = forms.HiddenInput
        kwargs["queryset"] = HedgeData.objects.all()
        super().__init__(*args, **kwargs)

    def get_display_value(self, value):
        data = self.clean(value)
        display_value = (
            f"{round(data.length_to_remove())} m / {round(data.length_to_plant())} m"
        )
        return display_value


class MoulinetteFormHaie(BaseMoulinetteForm):
    motif = forms.ChoiceField(
        label="Pour quelle raison la destruction de haie a-t-elle lieu ?",
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
    localisation_pac = forms.ChoiceField(
        label="Les haies à détruire sont-elles situées sur des parcelles agricoles déclarées à la PAC ?",
        widget=forms.RadioSelect,
        choices=LOCALISATION_PAC_CHOICES,
        required=True,
    )
    haies = HedgeDataChoiceField(
        label="Linéaire de haies à détruire / planter",
        required=True,
        error_messages={
            "required": """Aucune haie n’a été saisie. Cliquez sur le bouton ci-dessus pour
            localiser les haies à détruire."""
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
        localisation_pac = data.get("localisation_pac")
        haies = data.get("haies")

        if motif == "chemin_acces" and reimplantation == "remplacement":
            self.add_error(
                "reimplantation",
                """Le remplacement de la haie au même endroit est incompatible avec la
                raison « création d’un accès ». Modifiez l'une ou l'autre des réponses du formulaire.""",
            )

        elif motif == "amelioration_ecologique" and reimplantation == "non":
            self.add_error(
                "reimplantation",
                """La destruction de la haie sans réimplantation est incompatible avec la raison
                « amélioration écologique ». Modifiez l'une ou l'autre des réponses du formulaire.""",
            )

        if localisation_pac == "oui" and haies:
            on_pac_values = [h.is_on_pac for h in haies.hedges_to_remove()]
            if not any(on_pac_values):
                self.add_error(
                    "localisation_pac",
                    """Il est indiqué que « oui, au moins une des haies » est située
                    sur une parcelle PAC, mais aucune des haies saisies n’est marquée
                    comme située sur une parcelle PAC. Modifiez la réponse ou modifiez
                    les haies.""",
                )
        elif localisation_pac == "non" and haies:
            on_pac_values = [h.is_on_pac for h in haies.hedges_to_remove()]
            if any(on_pac_values):
                self.add_error(
                    "localisation_pac",
                    """Il est indiqué que « non, aucune des haies » n’est située sur
                    une parcelle PAC, mais au moins une des haies saisies est marquée
                    comme située sur une parcelle PAC. Modifiez la réponse ou modifiez
                    les haies ci-dessous.""",
                )

        return data

    def clean_haies(self):
        haies = self.cleaned_data["haies"]
        if haies.length_to_remove() == 0:
            self.add_error(
                "haies",
                "Merci de saisir au moins une haie à détruire.",
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
                        Toute intervention qui supprime définitivement la végétation : arrachage,
                        coupe à blanc sur essences qui ne recèpent pas (ex : chêne,
                        sorbier, noyer, merisier, bouleau, hêtre, tous les résineux…),
                        entretien sévère et récurrent, etc.
                        Toute intervention supprimant définitivement la végétation : arrachage ; « déplacement » de haie ;
                        coupe à blanc sur essences qui ne recèpent pas 
                        (<a href="https://www.notion.so/Liste-des-essences-et-leur-capacit-rec-per-1b6fe5fe47668041a5d9d22ac5be31e1" target="_blank" rel="noopener">voir liste</a>) ;
                        entretien sévère et récurrent ; etc.
                    </span>
                    """
                ),
            ),
            (
                "entretien",
                mark_safe(
                    """Entretien<br />
                    <span class="fr-hint-text">
                        Intervention qui permet la repousse durable de la végétation : élagage, taille,
                        coupe à blanc sur une essence capable de recéper (<a href="https://www.notion.so/Liste-des-essences-et-leur-capacit-rec-per-1b6fe5fe47668041a5d9d22ac5be31e1" target="_blank" rel="noopener">voir liste</a>), etc.
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
