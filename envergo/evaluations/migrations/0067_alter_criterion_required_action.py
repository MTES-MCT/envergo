# Generated by Django 3.2.12 on 2022-06-07 08:30

from django.db import migrations, models


def update_actions(apps, schema_editor):
    Criterion = apps.get_model("evaluations", "Criterion")
    Criterion.objects.filter(required_action="not_in_zh").update(
        required_action="surface_lt_1000"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0066_auto_20220602_0918"),
    ]

    operations = [
        migrations.AlterField(
            model_name="criterion",
            name="required_action",
            field=models.TextField(
                blank=True,
                choices=[
                    (
                        "surface_lt_1000",
                        "n'impacte pas plus de 1000\xa0m² de zone humide",
                    ),
                    (
                        "surface_lt_400",
                        "n'impacte pas plus de 400\xa0m² de zone inondable",
                    ),
                    (
                        "runoff_lt_10000",
                        "a une surface totale, augmentée de l'aire d'écoulement d'eaux de pluie interceptée, inférieure à 1\xa0ha",
                    ),
                ],
                verbose_name="Required action",
            ),
        ),
        migrations.RunPython(update_actions, migrations.RunPython.noop),
    ]
