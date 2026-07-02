from django.db import migrations


def create_icpe_instructor_actions(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")

    ActionToTake.objects.get_or_create(
        slug="mention_arrete_icpe_e",
        defaults={
            "type": "action",
            "target": "instructor",
            "order": 2,
            "label": "Mentionner dans l'arrêté le différé de réalisation des travaux",
            "details": "moulinette/actions_to_take/mention_arrete_icpe_e.html",
        },
    )
    ActionToTake.objects.get_or_create(
        slug="suspension_delai_icpe",
        defaults={
            "type": "action",
            "target": "instructor",
            "order": 1,
            "label": "Possible suspension de délai de l'instruction urbanisme",
            "details": "moulinette/actions_to_take/suspension_delai_icpe.html",
        },
    )
    ActionToTake.objects.get_or_create(
        slug="depot_dossier_icpe",
        defaults={
            "type": "action",
            "target": "petitioner",
            "order": 1,
            "label": "Déposer un dossier ICPE",
            "details": "moulinette/actions_to_take/depot_dossier_icpe.html",
        },
    )

    ActionToTake.objects.get_or_create(
        slug="pc_icpe_d",
        defaults={
            "type": "pc",
            "target": "instructor",
            "order": 1,
            "label": "La preuve de dépôt de la déclaration ICPE",
            "details": "moulinette/actions_to_take/pc_icpe_d.html",
            "documents_to_attach": ["PA37", "PC25"],
        },
    )
    ActionToTake.objects.get_or_create(
        slug="pc_icpe_e",
        defaults={
            "type": "pc",
            "target": "instructor",
            "order": 1,
            "label": "Le récépissé de la demande d'enregistrement ICPE",
            "details": "moulinette/actions_to_take/pc_icpe_e.html",
            "documents_to_attach": ["PA37-1", "PC25-1"],
        },
    )
    ActionToTake.objects.get_or_create(
        slug="pc_icpe_inconnu",
        defaults={
            "type": "pc",
            "target": "instructor",
            "order": 1,
            "label": "La preuve de dépôt de la demande ICPE",
            "details": "moulinette/actions_to_take/pc_icpe_inconnu.html",
            "documents_to_attach": [
                "PA37 (ICPE-D) ou PA37-1 (ICPE-E)",
                "PC25 (ICPE-D) ou PC25-1 (ICPE-E)",
            ],
        },
    )

    # Update existing actions that had no details template
    ActionToTake.objects.filter(slug="pc_cas_par_cas").update(
        details="moulinette/actions_to_take/pc_cas_par_cas.html",
    )
    ActionToTake.objects.filter(slug="depot_dossier_icpe").update(
        details="moulinette/actions_to_take/depot_dossier_icpe.html",
    )


def reverse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.filter(
        slug__in=[
            "mention_arrete_icpe_e",
            "suspension_delai_icpe",
            "depot_dossier_icpe",
            "pc_icpe_d",
            "pc_icpe_e",
            "pc_icpe_inconnu",
        ]
    ).delete()
    ActionToTake.objects.filter(slug="pc_cas_par_cas").update(details="")


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0120_add_icpe_instructor_actions"),
    ]

    operations = [
        migrations.RunPython(create_icpe_instructor_actions, reverse),
    ]
