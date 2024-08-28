# Generated by Django 4.2.13 on 2024-08-26 04:49

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0057_set_criteria_perimeters"),
    ]

    operations = [
        migrations.AlterField(
            model_name="moulinetteconfig",
            name="regulations_available",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("loi_sur_leau", "Loi sur l'eau"),
                        ("natura2000", "Natura 2000"),
                        ("eval_env", "Évaluation environnementale"),
                        ("sage", "Règlement de SAGE"),
                        ("conditionnalite_pac", "Conditionnalité PAC"),
                        ("dep", "Dérogation « espèces protégées »"),
                    ],
                    max_length=64,
                ),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="moulinettetemplate",
            name="key",
            field=models.CharField(
                choices=[
                    ("autorisation_urba_pa", "autorisation_urba_pa"),
                    (
                        "autorisation_urba_pa_lotissement",
                        "autorisation_urba_pa_lotissement",
                    ),
                    ("autorisation_urba_pc", "autorisation_urba_pc"),
                    (
                        "autorisation_urba_amenagement_dp",
                        "autorisation_urba_amenagement_dp",
                    ),
                    (
                        "autorisation_urba_construction_dp",
                        "autorisation_urba_construction_dp",
                    ),
                    ("autorisation_urba_none", "autorisation_urba_none"),
                    ("autorisation_urba_other", "autorisation_urba_other"),
                    (
                        "conditionnalite_pac/result_interdit.html",
                        "conditionnalite_pac/result_interdit.html",
                    ),
                    (
                        "conditionnalite_pac/result_non_soumis.html",
                        "conditionnalite_pac/result_non_soumis.html",
                    ),
                    (
                        "conditionnalite_pac/result_soumis.html",
                        "conditionnalite_pac/result_soumis.html",
                    ),
                    ("dep/result_soumis.html", "dep/result_soumis.html"),
                    (
                        "eval_env/aire_de_stationnement_cas_par_cas.html",
                        "eval_env/aire_de_stationnement_cas_par_cas.html",
                    ),
                    (
                        "eval_env/aire_de_stationnement_non_soumis.html",
                        "eval_env/aire_de_stationnement_non_soumis.html",
                    ),
                    (
                        "eval_env/autres_rubriques_non_disponible.html",
                        "eval_env/autres_rubriques_non_disponible.html",
                    ),
                    (
                        "eval_env/camping_cas_par_cas.html",
                        "eval_env/camping_cas_par_cas.html",
                    ),
                    (
                        "eval_env/camping_non_soumis.html",
                        "eval_env/camping_non_soumis.html",
                    ),
                    (
                        "eval_env/camping_systematique.html",
                        "eval_env/camping_systematique.html",
                    ),
                    (
                        "eval_env/clause_filet_clause_filet.html",
                        "eval_env/clause_filet_clause_filet.html",
                    ),
                    (
                        "eval_env/defrichement_deboisement_cas_par_cas.html",
                        "eval_env/defrichement_deboisement_cas_par_cas.html",
                    ),
                    (
                        "eval_env/defrichement_deboisement_non_soumis.html",
                        "eval_env/defrichement_deboisement_non_soumis.html",
                    ),
                    (
                        "eval_env/emprise_cas_par_cas.html",
                        "eval_env/emprise_cas_par_cas.html",
                    ),
                    (
                        "eval_env/emprise_non_soumis.html",
                        "eval_env/emprise_non_soumis.html",
                    ),
                    (
                        "eval_env/emprise_systematique.html",
                        "eval_env/emprise_systematique.html",
                    ),
                    (
                        "eval_env/photovoltaique_cas_par_cas_sol.html",
                        "eval_env/photovoltaique_cas_par_cas_sol.html",
                    ),
                    (
                        "eval_env/photovoltaique_cas_par_cas_toiture.html",
                        "eval_env/photovoltaique_cas_par_cas_toiture.html",
                    ),
                    (
                        "eval_env/photovoltaique_non_soumis.html",
                        "eval_env/photovoltaique_non_soumis.html",
                    ),
                    (
                        "eval_env/photovoltaique_non_soumis_ombriere.html",
                        "eval_env/photovoltaique_non_soumis_ombriere.html",
                    ),
                    (
                        "eval_env/photovoltaique_non_soumis_toiture.html",
                        "eval_env/photovoltaique_non_soumis_toiture.html",
                    ),
                    (
                        "eval_env/photovoltaique_systematique_sol.html",
                        "eval_env/photovoltaique_systematique_sol.html",
                    ),
                    (
                        "eval_env/photovoltaique_systematique_toiture.html",
                        "eval_env/photovoltaique_systematique_toiture.html",
                    ),
                    (
                        "eval_env/piste_cyclable_cas_par_cas.html",
                        "eval_env/piste_cyclable_cas_par_cas.html",
                    ),
                    (
                        "eval_env/piste_cyclable_non_soumis.html",
                        "eval_env/piste_cyclable_non_soumis.html",
                    ),
                    (
                        "eval_env/premier_boisement_cas_par_cas.html",
                        "eval_env/premier_boisement_cas_par_cas.html",
                    ),
                    (
                        "eval_env/premier_boisement_non_soumis.html",
                        "eval_env/premier_boisement_non_soumis.html",
                    ),
                    (
                        "eval_env/result_cas_par_cas.html",
                        "eval_env/result_cas_par_cas.html",
                    ),
                    (
                        "eval_env/result_non_active.html",
                        "eval_env/result_non_active.html",
                    ),
                    (
                        "eval_env/result_non_disponible.html",
                        "eval_env/result_non_disponible.html",
                    ),
                    (
                        "eval_env/result_non_soumis.html",
                        "eval_env/result_non_soumis.html",
                    ),
                    (
                        "eval_env/result_systematique.html",
                        "eval_env/result_systematique.html",
                    ),
                    (
                        "eval_env/route_publique_cas_par_cas.html",
                        "eval_env/route_publique_cas_par_cas.html",
                    ),
                    (
                        "eval_env/route_publique_non_soumis.html",
                        "eval_env/route_publique_non_soumis.html",
                    ),
                    (
                        "eval_env/route_publique_systematique.html",
                        "eval_env/route_publique_systematique.html",
                    ),
                    (
                        "eval_env/sport_loisir_culture_cas_par_cas.html",
                        "eval_env/sport_loisir_culture_cas_par_cas.html",
                    ),
                    (
                        "eval_env/sport_loisir_culture_non_soumis.html",
                        "eval_env/sport_loisir_culture_non_soumis.html",
                    ),
                    (
                        "eval_env/sport_loisir_culture_non_soumis_lt1000.html",
                        "eval_env/sport_loisir_culture_non_soumis_lt1000.html",
                    ),
                    (
                        "eval_env/surface_plancher_cas_par_cas.html",
                        "eval_env/surface_plancher_cas_par_cas.html",
                    ),
                    (
                        "eval_env/surface_plancher_non_soumis.html",
                        "eval_env/surface_plancher_non_soumis.html",
                    ),
                    (
                        "eval_env/terrain_assiette_cas_par_cas.html",
                        "eval_env/terrain_assiette_cas_par_cas.html",
                    ),
                    (
                        "eval_env/terrain_assiette_non_concerne.html",
                        "eval_env/terrain_assiette_non_concerne.html",
                    ),
                    (
                        "eval_env/terrain_assiette_non_soumis.html",
                        "eval_env/terrain_assiette_non_soumis.html",
                    ),
                    (
                        "eval_env/terrain_assiette_systematique.html",
                        "eval_env/terrain_assiette_systematique.html",
                    ),
                    (
                        "eval_env/voie_privee_cas_par_cas.html",
                        "eval_env/voie_privee_cas_par_cas.html",
                    ),
                    (
                        "eval_env/voie_privee_non_soumis.html",
                        "eval_env/voie_privee_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/autres_rubriques_non_disponible.html",
                        "loi_sur_leau/autres_rubriques_non_disponible.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_avec_bv_action_requise.html",
                        "loi_sur_leau/ecoulement_avec_bv_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_avec_bv_action_requise_probable_1ha.html",
                        "loi_sur_leau/ecoulement_avec_bv_action_requise_probable_1ha.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_avec_bv_non_soumis.html",
                        "loi_sur_leau/ecoulement_avec_bv_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_avec_bv_soumis.html",
                        "loi_sur_leau/ecoulement_avec_bv_soumis.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_sans_bv_action_requise.html",
                        "loi_sur_leau/ecoulement_sans_bv_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_sans_bv_non_soumis.html",
                        "loi_sur_leau/ecoulement_sans_bv_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/ecoulement_sans_bv_soumis.html",
                        "loi_sur_leau/ecoulement_sans_bv_soumis.html",
                    ),
                    (
                        "loi_sur_leau/result_action_requise.html",
                        "loi_sur_leau/result_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/result_non_active.html",
                        "loi_sur_leau/result_non_active.html",
                    ),
                    (
                        "loi_sur_leau/result_non_disponible.html",
                        "loi_sur_leau/result_non_disponible.html",
                    ),
                    (
                        "loi_sur_leau/result_non_soumis.html",
                        "loi_sur_leau/result_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/result_soumis.html",
                        "loi_sur_leau/result_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise.html",
                        "loi_sur_leau/zone_humide_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise_dans_doute.html",
                        "loi_sur_leau/zone_humide_action_requise_dans_doute.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise_proche.html",
                        "loi_sur_leau/zone_humide_action_requise_proche.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise_tout_dpt.html",
                        "loi_sur_leau/zone_humide_action_requise_tout_dpt.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_non_concerne.html",
                        "loi_sur_leau/zone_humide_non_concerne.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_non_soumis.html",
                        "loi_sur_leau/zone_humide_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_soumis.html",
                        "loi_sur_leau/zone_humide_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_action_requise.html",
                        "loi_sur_leau/zone_inondable_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_action_requise_dans_doute.html",
                        "loi_sur_leau/zone_inondable_action_requise_dans_doute.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_non_concerne.html",
                        "loi_sur_leau/zone_inondable_non_concerne.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_non_soumis.html",
                        "loi_sur_leau/zone_inondable_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_soumis.html",
                        "loi_sur_leau/zone_inondable_soumis.html",
                    ),
                    (
                        "natura2000/autorisation_urba_a_verifier.html",
                        "natura2000/autorisation_urba_a_verifier.html",
                    ),
                    (
                        "natura2000/autorisation_urba_non_soumis.html",
                        "natura2000/autorisation_urba_non_soumis.html",
                    ),
                    (
                        "natura2000/autorisation_urba_non_soumis_lotissement.html",
                        "natura2000/autorisation_urba_non_soumis_lotissement.html",
                    ),
                    (
                        "natura2000/autorisation_urba_soumis.html",
                        "natura2000/autorisation_urba_soumis.html",
                    ),
                    (
                        "natura2000/iota_iota_a_verifier.html",
                        "natura2000/iota_iota_a_verifier.html",
                    ),
                    (
                        "natura2000/iota_non_soumis.html",
                        "natura2000/iota_non_soumis.html",
                    ),
                    ("natura2000/iota_soumis.html", "natura2000/iota_soumis.html"),
                    (
                        "natura2000/lotissement_non_soumis.html",
                        "natura2000/lotissement_non_soumis.html",
                    ),
                    (
                        "natura2000/lotissement_soumis_dedans.html",
                        "natura2000/lotissement_soumis_dedans.html",
                    ),
                    (
                        "natura2000/lotissement_soumis_proximite_immediate.html",
                        "natura2000/lotissement_soumis_proximite_immediate.html",
                    ),
                    (
                        "natura2000/result_a_verifier.html",
                        "natura2000/result_a_verifier.html",
                    ),
                    (
                        "natura2000/result_action_requise.html",
                        "natura2000/result_action_requise.html",
                    ),
                    (
                        "natura2000/result_iota_a_verifier.html",
                        "natura2000/result_iota_a_verifier.html",
                    ),
                    (
                        "natura2000/result_non_active.html",
                        "natura2000/result_non_active.html",
                    ),
                    (
                        "natura2000/result_non_concerne.html",
                        "natura2000/result_non_concerne.html",
                    ),
                    (
                        "natura2000/result_non_disponible.html",
                        "natura2000/result_non_disponible.html",
                    ),
                    (
                        "natura2000/result_non_soumis.html",
                        "natura2000/result_non_soumis.html",
                    ),
                    ("natura2000/result_soumis.html", "natura2000/result_soumis.html"),
                    (
                        "natura2000/zone_humide_action_requise_dans_doute.html",
                        "natura2000/zone_humide_action_requise_dans_doute.html",
                    ),
                    (
                        "natura2000/zone_humide_action_requise_proche.html",
                        "natura2000/zone_humide_action_requise_proche.html",
                    ),
                    (
                        "natura2000/zone_humide_non_concerne.html",
                        "natura2000/zone_humide_non_concerne.html",
                    ),
                    (
                        "natura2000/zone_humide_non_soumis.html",
                        "natura2000/zone_humide_non_soumis.html",
                    ),
                    (
                        "natura2000/zone_humide_non_soumis_dans_doute.html",
                        "natura2000/zone_humide_non_soumis_dans_doute.html",
                    ),
                    (
                        "natura2000/zone_humide_non_soumis_proche.html",
                        "natura2000/zone_humide_non_soumis_proche.html",
                    ),
                    (
                        "natura2000/zone_humide_soumis.html",
                        "natura2000/zone_humide_soumis.html",
                    ),
                    (
                        "natura2000/zone_inondable_non_concerne.html",
                        "natura2000/zone_inondable_non_concerne.html",
                    ),
                    (
                        "natura2000/zone_inondable_non_soumis.html",
                        "natura2000/zone_inondable_non_soumis.html",
                    ),
                    (
                        "natura2000/zone_inondable_soumis.html",
                        "natura2000/zone_inondable_soumis.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_dans_doute_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_dans_doute_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_proche_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_proche_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_tout_dpt_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_tout_dpt_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_interdit.html",
                        "sage/interdiction_impact_zh_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_a_verifier.html",
                        "sage/interdiction_impact_zh_iota_a_verifier.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_action_requise_dans_doute_interdit.html",
                        "sage/interdiction_impact_zh_iota_action_requise_dans_doute_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_action_requise_interdit.html",
                        "sage/interdiction_impact_zh_iota_action_requise_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_action_requise_proche_interdit.html",
                        "sage/interdiction_impact_zh_iota_action_requise_proche_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_action_requise_tout_dpt_interdit.html",
                        "sage/interdiction_impact_zh_iota_action_requise_tout_dpt_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_interdit.html",
                        "sage/interdiction_impact_zh_iota_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_non_soumis.html",
                        "sage/interdiction_impact_zh_iota_non_soumis.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_iota_non_soumis_dehors.html",
                        "sage/interdiction_impact_zh_iota_non_soumis_dehors.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_non_soumis.html",
                        "sage/interdiction_impact_zh_non_soumis.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_non_soumis_dehors.html",
                        "sage/interdiction_impact_zh_non_soumis_dehors.html",
                    ),
                    ("sage/result_a_verifier.html", "sage/result_a_verifier.html"),
                    (
                        "sage/result_action_requise.html",
                        "sage/result_action_requise.html",
                    ),
                    ("sage/result_interdit.html", "sage/result_interdit.html"),
                    ("sage/result_non_active.html", "sage/result_non_active.html"),
                    ("sage/result_non_concerne.html", "sage/result_non_concerne.html"),
                    (
                        "sage/result_non_disponible.html",
                        "sage/result_non_disponible.html",
                    ),
                    ("sage/result_non_soumis.html", "sage/result_non_soumis.html"),
                ],
                max_length=512,
                verbose_name="Key",
            ),
        ),
        migrations.AlterField(
            model_name="regulation",
            name="regulation",
            field=models.CharField(
                choices=[
                    ("loi_sur_leau", "Loi sur l'eau"),
                    ("natura2000", "Natura 2000"),
                    ("eval_env", "Évaluation environnementale"),
                    ("sage", "Règlement de SAGE"),
                    ("conditionnalite_pac", "Conditionnalité PAC"),
                    ("dep", "Dérogation « espèces protégées »"),
                ],
                max_length=64,
                verbose_name="Regulation",
            ),
        ),
    ]
