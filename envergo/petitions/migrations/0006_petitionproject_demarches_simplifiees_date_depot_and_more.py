# Generated by Django 4.2.19 on 2025-03-18 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0005_add_meilleur_emplacement_to_all_petition_projects"),
    ]

    operations = [
        migrations.AddField(
            model_name="petitionproject",
            name="demarches_simplifiees_date_depot",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Date de dépôt dans Démarches Simplifiées",
            ),
        ),
        migrations.AlterField(
            model_name="petitionproject",
            name="onagre_number",
            field=models.CharField(
                blank=True, max_length=64, verbose_name="Référence ONAGRE du dossier"
            ),
        ),
    ]
