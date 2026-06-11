from django.db import migrations


def create_depot_pac_icpe(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.get_or_create(
        slug="depot_pac_icpe",
        defaults={
            "type": "action",
            "target": "petitioner",
            "order": 1,
            "label": "Déposer un porter-à-connaissance ICPE",
            "details": "moulinette/actions_to_take/depot_pac_icpe.html",
        },
    )


def reverse(apps, schema_editor):
    ActionToTake = apps.get_model("moulinette", "ActionToTake")
    ActionToTake.objects.filter(slug="depot_pac_icpe").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0122_add_depot_pac_icpe_choice"),
    ]

    operations = [
        migrations.RunPython(create_depot_pac_icpe, reverse),
    ]
