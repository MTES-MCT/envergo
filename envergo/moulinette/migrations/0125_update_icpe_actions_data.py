from django.db import migrations


def update_icpe_actions(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")

    ActionToTake.objects.filter(slug="pc_icpe_d").update(
        documents_to_attach=["PA37", "PC25"],
    )
    ActionToTake.objects.filter(slug="pc_icpe_e").update(
        documents_to_attach=["PA37-1", "PC25-1"],
    )
    ActionToTake.objects.filter(slug="pc_icpe_inconnu").update(
        documents_to_attach=[
            "PA37 (ICPE-D) ou PA37-1 (ICPE-E)",
            "PC25 (ICPE-D) ou PC25-1 (ICPE-E)",
        ],
    )
    ActionToTake.objects.filter(slug="depot_dossier_icpe").update(
        details="moulinette/actions_to_take/depot_dossier_icpe.html",
    )


def reverse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")

    ActionToTake.objects.filter(
        slug__in=["pc_icpe_d", "pc_icpe_e", "pc_icpe_inconnu"]
    ).update(documents_to_attach=[])
    ActionToTake.objects.filter(slug="depot_dossier_icpe").update(details="")


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0124_create_icpe_criterion"),
    ]

    operations = [
        migrations.RunPython(update_icpe_actions, reverse),
    ]
