# Generated by Django 4.2 on 2024-01-26 14:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0045_criterion_evaluator_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="criterion",
            name="evaluator_settings",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Evaluator settings"
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
                        "loi_sur_leau/zone_humide_non_soumis.html",
                        "loi_sur_leau/zone_humide_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_action_requise.html",
                        "loi_sur_leau/zone_inondable_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_non_concerne.html",
                        "loi_sur_leau/zone_inondable_non_concerne.html",
                    ),
                    (
                        "loi_sur_leau/autres_rubriques_non_disponible.html",
                        "loi_sur_leau/autres_rubriques_non_disponible.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise_dans_doute.html",
                        "loi_sur_leau/zone_humide_action_requise_dans_doute.html",
                    ),
                    (
                        "loi_sur_leau/ruissellement_action_requise.html",
                        "loi_sur_leau/ruissellement_action_requise.html",
                    ),
                    (
                        "loi_sur_leau/ruissellement_non_soumis.html",
                        "loi_sur_leau/ruissellement_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/ruissellement_soumis.html",
                        "loi_sur_leau/ruissellement_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_soumis.html",
                        "loi_sur_leau/zone_inondable_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_inondable_non_soumis.html",
                        "loi_sur_leau/zone_inondable_non_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_soumis.html",
                        "loi_sur_leau/zone_humide_soumis.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise_proche.html",
                        "loi_sur_leau/zone_humide_action_requise_proche.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_non_concerne.html",
                        "loi_sur_leau/zone_humide_non_concerne.html",
                    ),
                    (
                        "loi_sur_leau/zone_humide_action_requise.html",
                        "loi_sur_leau/zone_humide_action_requise.html",
                    ),
                    (
                        "natura2000/zone_humide_non_soumis.html",
                        "natura2000/zone_humide_non_soumis.html",
                    ),
                    (
                        "natura2000/autorisation_urba_non_soumis.html",
                        "natura2000/autorisation_urba_non_soumis.html",
                    ),
                    (
                        "natura2000/zone_inondable_non_concerne.html",
                        "natura2000/zone_inondable_non_concerne.html",
                    ),
                    (
                        "natura2000/autorisation_urba_soumis.html",
                        "natura2000/autorisation_urba_soumis.html",
                    ),
                    ("natura2000/iota_soumis.html", "natura2000/iota_soumis.html"),
                    (
                        "natura2000/zone_humide_non_soumis_dans_doute.html",
                        "natura2000/zone_humide_non_soumis_dans_doute.html",
                    ),
                    (
                        "natura2000/zone_humide_action_requise_dans_doute.html",
                        "natura2000/zone_humide_action_requise_dans_doute.html",
                    ),
                    (
                        "natura2000/autorisation_urba_non_soumis_lotissement.html",
                        "natura2000/autorisation_urba_non_soumis_lotissement.html",
                    ),
                    (
                        "natura2000/lotissement_non_soumis.html",
                        "natura2000/lotissement_non_soumis.html",
                    ),
                    (
                        "natura2000/iota_iota_a_verifier.html",
                        "natura2000/iota_iota_a_verifier.html",
                    ),
                    (
                        "natura2000/lotissement_soumis_dedans.html",
                        "natura2000/lotissement_soumis_dedans.html",
                    ),
                    (
                        "natura2000/iota_non_soumis.html",
                        "natura2000/iota_non_soumis.html",
                    ),
                    (
                        "natura2000/zone_inondable_soumis.html",
                        "natura2000/zone_inondable_soumis.html",
                    ),
                    (
                        "natura2000/zone_inondable_non_soumis.html",
                        "natura2000/zone_inondable_non_soumis.html",
                    ),
                    (
                        "natura2000/zone_humide_soumis.html",
                        "natura2000/zone_humide_soumis.html",
                    ),
                    (
                        "natura2000/zone_humide_action_requise_proche.html",
                        "natura2000/zone_humide_action_requise_proche.html",
                    ),
                    (
                        "natura2000/zone_humide_non_soumis_proche.html",
                        "natura2000/zone_humide_non_soumis_proche.html",
                    ),
                    (
                        "natura2000/zone_humide_non_concerne.html",
                        "natura2000/zone_humide_non_concerne.html",
                    ),
                    (
                        "natura2000/autorisation_urba_a_verifier.html",
                        "natura2000/autorisation_urba_a_verifier.html",
                    ),
                    (
                        "natura2000/lotissement_soumis_proximite_immediate.html",
                        "natura2000/lotissement_soumis_proximite_immediate.html",
                    ),
                    (
                        "eval_env/autres_rubriques_non_disponible.html",
                        "eval_env/autres_rubriques_non_disponible.html",
                    ),
                    (
                        "eval_env/surface_plancher_non_soumis.html",
                        "eval_env/surface_plancher_non_soumis.html",
                    ),
                    (
                        "eval_env/clause_filet_clause_filet.html",
                        "eval_env/clause_filet_clause_filet.html",
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
                        "eval_env/terrain_assiette_systematique.html",
                        "eval_env/terrain_assiette_systematique.html",
                    ),
                    (
                        "eval_env/terrain_assiette_cas_par_cas.html",
                        "eval_env/terrain_assiette_cas_par_cas.html",
                    ),
                    (
                        "eval_env/surface_plancher_cas_par_cas.html",
                        "eval_env/surface_plancher_cas_par_cas.html",
                    ),
                    (
                        "eval_env/terrain_assiette_non_soumis.html",
                        "eval_env/terrain_assiette_non_soumis.html",
                    ),
                    (
                        "eval_env/terrain_assiette_non_concerne.html",
                        "eval_env/terrain_assiette_non_concerne.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_interdit.html",
                    ),
                    (
                        "sage/zone_humide_gmre_56_action_requise_proche_interdit.html",
                        "sage/zone_humide_gmre_56_action_requise_proche_interdit.html",
                    ),
                    (
                        "sage/zone_humide_vie_jaunay_85_action_requise_proche_interdit.html",
                        "sage/zone_humide_vie_jaunay_85_action_requise_proche_interdit.html",
                    ),
                    (
                        "sage/zone_humide_vie_jaunay_85_non_soumis.html",
                        "sage/zone_humide_vie_jaunay_85_non_soumis.html",
                    ),
                    (
                        "sage/zone_humide_vie_jaunay_85_interdit.html",
                        "sage/zone_humide_vie_jaunay_85_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_dans_doute_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_dans_doute_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_action_requise_proche_interdit.html",
                        "sage/interdiction_impact_zh_action_requise_proche_interdit.html",
                    ),
                    (
                        "sage/zone_humide_vie_jaunay_85_non_soumis_dehors.html",
                        "sage/zone_humide_vie_jaunay_85_non_soumis_dehors.html",
                    ),
                    (
                        "sage/zone_humide_gmre_56_action_requise_dans_doute_interdit.html",
                        "sage/zone_humide_gmre_56_action_requise_dans_doute_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_interdit.html",
                        "sage/interdiction_impact_zh_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_non_soumis.html",
                        "sage/interdiction_impact_zh_non_soumis.html",
                    ),
                    (
                        "sage/zone_humide_gmre_56_interdit.html",
                        "sage/zone_humide_gmre_56_interdit.html",
                    ),
                    (
                        "sage/zone_humide_vie_jaunay_85_action_requise_interdit.html",
                        "sage/zone_humide_vie_jaunay_85_action_requise_interdit.html",
                    ),
                    (
                        "sage/interdiction_impact_zh_non_soumis_dehors.html",
                        "sage/interdiction_impact_zh_non_soumis_dehors.html",
                    ),
                    (
                        "sage/zone_humide_gmre_56_non_concerne.html",
                        "sage/zone_humide_gmre_56_non_concerne.html",
                    ),
                ],
                max_length=512,
                verbose_name="Key",
            ),
        ),
    ]
