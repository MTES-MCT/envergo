from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q


class DemarcheConfig(models.Model):
    demarche_numerique_number = models.IntegerField(
        "Numéro de la « Démarche numérique »",
        unique=True,
        help_text="Vous trouverez ce numéro en haut à droite de la carte de votre démarche dans la liste suivante : "
        '<a href="https://demarche.numerique.gouv.fr/admin/procedures" target="_blank" rel="noopener">'
        "https://demarche.numerique.gouv.fr/admin/procedures</a>",
    )

    display_name = models.CharField(
        "Nom de la démarche",
        blank=True,
        null=True,
        help_text="Pour affichage dans l’administration Django uniquement",
    )

    pre_fill_config = models.JSONField(
        "Configuration pré-remplissage sur « Démarche numérique »",
        blank=True,
        null=False,
        default=list,
    )

    display_fields = models.JSONField(
        blank=True,
        null=False,
        default=dict,
    )

    class Meta:
        verbose_name = "Démarche Numérique"
        verbose_name_plural = "Démarches Numériques"
        constraints = (
            CheckConstraint(
                check=Q(display_fields__project_url__isnull=False),
                name="project_url_id_required",
            ),
        )

    def clean(self):
        if not isinstance(self.pre_fill_config, list):
            raise ValidationError(
                {
                    "pre_fill_config": "Cette configuration doit être une liste de champs"
                    " (ou d'annotations privées) à pré-remplir"
                }
            )

        availables_sources = {
            tup[0]
            for value in self.get_demarche_numerique_value_sources().values()
            for tup in value
        }
        for field in self.pre_fill_config:
            if not isinstance(field, dict) or "id" not in field or "value" not in field:
                raise ValidationError(
                    {
                        "pre_fill_config": "Chaque champ (ou annotation privée) doit contenir"
                        " au moins l'id côté « Démarche numérique » et la "
                        "source de la valeur côté guichet unique de la haie."
                    }
                )
            if field["value"] not in availables_sources:
                raise ValidationError(
                    {
                        "pre_fill_config": f"La source de la valeur {field['value']} n'est pas "
                        f"valide pour le champ dont l'id est {field['id']}"
                    }
                )
            if "mapping" in field and not isinstance(field["mapping"], dict):
                raise ValidationError(
                    {
                        "pre_fill_config": f"Le mapping du champ dont l'id est {field['id']} "
                        f"doit être un dictionnaire."
                    }
                )

    def __str__(self):
        return f"{self.display_name} ({self.demarche_numerique_number})"

    @classmethod
    def get_demarche_numerique_value_sources(cls):
        from envergo.moulinette.forms import (
            MoulinetteFormHaieHRU,
            MoulinetteFormHaieRU,
            TriageFormHaie,
        )
        from envergo.moulinette.models import MoulinetteHaie, Regulation

        """Populate a list of available sources for the pre-fill configuration of the Démarche numérique

        This method aggregates :
         * some well known values (e.g. moulinette_url)
         * the fields of all the forms that the user may have to fill in the guichet unique de la haie :
            * the main form
            * the triage form
            * the forms of the criteria of involved regulations
         * the results of the regulations
        """

        regulations = Regulation.objects.filter(
            regulation__in=MoulinetteHaie.REGULATIONS
        ).prefetch_related("criteria")
        triage_form_fields = {
            (key, field.label) for key, field in TriageFormHaie.base_fields.items()
        }
        main_form_fields = {
            (key, field.label)
            for form_class in (MoulinetteFormHaieRU, MoulinetteFormHaieHRU)
            for key, field in form_class.base_fields.items()
        }

        identified_sources = {
            ("url_moulinette", "Url de la simulation"),
            ("url_projet", "Url du projet de dossier"),
            ("ref_projet", "Référence du projet de dossier"),
            (
                "plantation_adequate",
                "Les conditions d’acceptabilité de la plantation sont toutes respectées (booléen)",
            ),
            ("category", "Catégorie du projet (ru, hru ou l350_3)"),
            (
                "from_multi_category",
                "Le projet provient-il d'une simulation comportant plusieurs catégories",
            ),
            (
                "original_multi_category_moulinette_url",
                "Url de la simulation initiale comportant plusieurs catégories le cas échéant",
            ),
            ("vieil_arbre", "Présence de vieux arbres fissurés ou à cavité (booléen)"),
            ("proximite_mare", "Proximité d'une mare (booléen)"),
            (
                "sur_talus_d",
                "Au moins une haie à détruire est marquée “sur_talus” (booléen)",
            ),
            (
                "sur_talus_p",
                "Au moins une haie à planter est marquée “sur_talus” (booléen)",
            ),
        }

        available_sources = {
            "Fléchage": triage_form_fields,
            "Questions principales": main_form_fields,
        }

        regulation_results = set()
        criteria_results = set()

        for regulation in regulations.all():
            regulation_sources = set()
            regulation_results.add(
                (
                    f"{regulation.slug}.result",
                    f"Résultat de la réglementation {regulation.regulation}",
                )
            )
            for criterion in regulation.criteria.all():
                criterion_result_slug_code = (
                    f"{regulation.slug}.{criterion.slug}.result_code"
                )
                if criterion_result_slug_code not in dict(criteria_results):
                    criteria_results.add(
                        (
                            criterion_result_slug_code,
                            f"Code de résultat du critère {criterion.backend_title} "
                            f"de la réglementation {regulation.regulation}",
                        )
                    )
                form_class = criterion.evaluator.form_class
                if form_class:
                    regulation_sources.update(
                        {
                            (key, field.label)
                            for key, field in form_class.base_fields.items()
                        }
                    )

            if regulation_sources:
                available_sources[f'Questions complémentaires "{regulation.title}"'] = (
                    regulation_sources
                )

        available_sources["Résultats réglementation"] = regulation_results
        available_sources["Résultats des critères"] = criteria_results
        available_sources["Variables projet"] = identified_sources

        return available_sources
