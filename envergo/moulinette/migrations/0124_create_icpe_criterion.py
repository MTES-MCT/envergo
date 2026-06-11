from django.db import migrations


def create_icpe_criterion(apps, schema_editor):
    Map = apps.get_model("geodata", "Map")
    Regulation = apps.get_model("moulinette", "Regulation")
    Criterion = apps.get_model("moulinette", "Criterion")

    try:
        activation_map = Map.objects.get(name="France")
    except Map.DoesNotExist:
        return

    try:
        regulation = Regulation.objects.get(regulation="eval_env")
    except Regulation.DoesNotExist:
        return

    Criterion.objects.get_or_create(
        evaluator="envergo.moulinette.regulations.evalenv.ICPE",
        activation_map=activation_map,
        regulation=regulation,
        defaults={
            "backend_title": "ICPE cas par cas (staff-only)",
            "title": "Installation classée (ICPE)",
            "subtitle": "Examen au cas par cas",
            "is_optional": True,
            "is_staff_only": True,
            "weight": 100,
        },
    )


def reverse(apps, schema_editor):
    Criterion = apps.get_model("moulinette", "Criterion")
    Criterion.objects.filter(
        evaluator="envergo.moulinette.regulations.evalenv.ICPE",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0123_create_depot_pac_icpe"),
        ("geodata", "0029_merge_20260413_1454"),
    ]

    operations = [
        migrations.RunPython(create_icpe_criterion, reverse),
    ]
