# Generated by Django 3.2.6 on 2022-01-06 13:46

from django.db import migrations


def set_criterions_results(apps, schema_editor):
    Criterion = apps.get_model("evaluations", "Criterion")
    very_likely = 4
    likely = 3
    possible = 2

    soumis = 1
    non_soumis = 2
    action_requise = 3

    for criterion in Criterion.objects.all():
        if criterion.probability == very_likely:
            criterion.result = soumis
        else:
            criterion.result = non_soumis
        criterion.save()


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0046_criterion_required_action"),
    ]

    operations = [
        migrations.RunPython(set_criterions_results, migrations.RunPython.noop),
    ]
