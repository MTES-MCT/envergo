from django.db import migrations


def rename_template_keys(apps, schema_editor):
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_a_verifier_creation.html"
    ).update(key="eval_env/icpe_a_verifier.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_a_verifier_modification.html"
    ).update(key="eval_env/icpe_a_verifier_modif.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_a_verifier_sans_pac.html"
    ).update(key="eval_env/icpe_a_verifier.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_cas_par_cas_creation.html"
    ).update(key="eval_env/icpe_cas_par_cas.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_cas_par_cas_modif.html"
    ).delete()
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_non_soumis_declaration.html"
    ).delete()
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_non_soumis_declaration_sans_pac.html"
    ).delete()
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_non_soumis_sans_pac.html"
    ).update(key="eval_env/icpe_non_soumis.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_non_soumis_pas_icpe.html"
    ).update(key="eval_env/icpe_non_soumis.html")


def reverse(apps, schema_editor):
    MoulinetteTemplate = apps.get_model("moulinette", "MoulinetteTemplate")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_a_verifier.html"
    ).update(key="eval_env/icpe_a_verifier_creation.html")
    MoulinetteTemplate.objects.filter(
        key="eval_env/icpe_a_verifier_modif.html"
    ).update(key="eval_env/icpe_a_verifier_modification.html")


class Migration(migrations.Migration):

    dependencies = [
        ("moulinette", "0126_create_non_depot_lse"),
    ]

    operations = [
        migrations.RunPython(rename_template_keys, reverse),
    ]
