from django.db import migrations


def create_non_depot_lse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.get_or_create(
        slug="non_depot_lse",
        defaults={
            "type": "action",
            "target": "petitioner",
            "order": 2,
            "label": "Ne pas déposer de dossier Loi sur l'eau",
            "details": "moulinette/actions_to_take/non_depot_lse.html",
        },
    )


def reverse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.filter(slug="non_depot_lse").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0125_update_icpe_actions_data"),
    ]

    operations = [
        migrations.RunPython(create_non_depot_lse, reverse),
    ]
