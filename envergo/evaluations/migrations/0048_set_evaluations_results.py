# Generated by Django 3.2.6 on 2022-01-06 13:52

from django.db import migrations

soumis = 1
non_soumis = 2
action_requise = 3

very_likely = 4


def set_evaluations_results(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")

    evals = Evaluation.objects.prefetch_related("criterions")
    for eval in evals:

        if eval.global_probability == very_likely:
            eval.result = soumis
        else:
            eval.result = non_soumis
        eval.save()


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0047_set_criterions_results"),
    ]

    operations = [
        migrations.RunPython(set_evaluations_results, migrations.RunPython.noop),
    ]
