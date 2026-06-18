"""Rename species fields and models for clarity.

- taxref_ids → cd_noms (holds cd_nom values, not generic "IDs")
- group → adhoc_group (ad-hoc classification from data providers)
- taxref_group → group (official TaxRef GROUP2_INPN, promoted to main name)
- SpeciesMapFile → SpeciesHabitatFile
- SpeciesMap → SpeciesHabitat
- species_map_file → species_habitat_file
- related_name "species_maps" → "habitats"
"""

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0030_species_ru_fields"),
    ]

    operations = [
        # --- Field renames on Species ---
        migrations.RenameField(
            model_name="species",
            old_name="taxref_ids",
            new_name="cd_noms",
        ),
        # Free the "group" name first
        migrations.RenameField(
            model_name="species",
            old_name="group",
            new_name="adhoc_group",
        ),
        # Now take the freed name
        migrations.RenameField(
            model_name="species",
            old_name="taxref_group",
            new_name="group",
        ),
        # --- Model renames ---
        # Rename FK target first (SpeciesMap has a FK to SpeciesMapFile)
        migrations.RenameModel(
            old_name="SpeciesMapFile",
            new_name="SpeciesHabitatFile",
        ),
        migrations.RenameModel(
            old_name="SpeciesMap",
            new_name="SpeciesHabitat",
        ),
        # --- FK field rename ---
        migrations.RenameField(
            model_name="specieshabitat",
            old_name="species_map_file",
            new_name="species_habitat_file",
        ),
        # --- Update related_names from "species_maps" to "habitats" ---
        migrations.AlterField(
            model_name="specieshabitat",
            name="species",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="habitats",
                to="hedges.species",
                verbose_name="Espèce",
            ),
        ),
        migrations.AlterField(
            model_name="specieshabitat",
            name="map",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="habitats",
                to="geodata.map",
                verbose_name="Carte",
            ),
        ),
        migrations.AlterField(
            model_name="specieshabitat",
            name="species_habitat_file",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="habitats",
                to="hedges.specieshabitatfile",
                verbose_name="Importé par",
            ),
        ),
        # --- Update verbose_names on renamed Species fields ---
        migrations.AlterField(
            model_name="species",
            name="cd_noms",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                null=True,
                size=None,
                verbose_name="CD_NOM (TaxRef)",
            ),
        ),
        migrations.AlterField(
            model_name="species",
            name="group",
            field=models.CharField(
                blank=True, max_length=128, verbose_name="Groupe"
            ),
        ),
        # --- Update Meta verbose_names ---
        migrations.AlterModelOptions(
            name="specieshabitat",
            options={
                "verbose_name": "Habitat d'espèce",
                "verbose_name_plural": "Habitats d'espèces",
            },
        ),
        migrations.AlterModelOptions(
            name="specieshabitatfile",
            options={
                "verbose_name": "Fichier d'habitat d'espèce",
                "verbose_name_plural": "Fichiers d'habitat d'espèces",
            },
        ),
    ]
