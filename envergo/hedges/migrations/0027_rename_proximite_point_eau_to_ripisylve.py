import django.contrib.postgres.fields
from django.db import migrations, models


def update_speciesmap_hedge_properties(apps, schema_editor):
    schema_editor.execute(
        "UPDATE hedges_speciesmap "
        "SET hedge_properties = array_replace(hedge_properties, 'proximite_point_eau', 'ripisylve') "
        "WHERE 'proximite_point_eau' = ANY(hedge_properties)"
    )

def switch_proximite_point_eau_to_ripisylve(apps, schema_editor):
    schema_editor.execute(
        'UPDATE hedges_hedgedata '
        'SET data = REPLACE(data::text, \'"proximite_point_eau"\', \'"ripisylve"\')::jsonb '
        'WHERE data::text LIKE \'%%proximite_point_eau%%\''
    )

class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0026_alter_speciesmap_hedge_types"),
    ]

    operations = [
        migrations.RunPython(
            update_speciesmap_hedge_properties,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="speciesmap",
            name="hedge_properties",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("proximite_mare", "Mare à moins de 200\xa0m"),
                        ("ripisylve", "En bordure de cours d'eau ou de plan d'eau (haie ripisylve)"),
                        (
                            "connexion_boisement",
                            "Connectée à un boisement ou à une autre haie",
                        ),
                        (
                            "vieil_arbre",
                            "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
                        ),
                    ],
                    max_length=32,
                ),
                default=list,
                help_text="Propriétés requises par l'espèce",
                size=None,
                verbose_name="Propriétés de la haie",
            ),
        ),
        migrations.RunPython(
            switch_proximite_point_eau_to_ripisylve,
            migrations.RunPython.noop
        ),
    ]
