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
            "order": 2,
            "label": "Déposer un dossier ICPE",
            "details": "",
        },
    )

    # Add template to pc_cas_par_cas (exists but has no details template)
    ActionToTake.objects.filter(slug="pc_cas_par_cas").update(
        details="moulinette/actions_to_take/pc_cas_par_cas.html",
    )


def reverse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.filter(
        slug__in=["mention_arrete_icpe_e", "suspension_delai_icpe", "depot_dossier_icpe"]
    ).delete()
    ActionToTake.objects.filter(slug="pc_cas_par_cas").update(details="")


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0120_add_icpe_instructor_actions"),
    ]

    operations = [
        migrations.RunPython(create_icpe_instructor_actions, reverse),
    ]
