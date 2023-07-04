# Generated by Django 4.2 on 2023-07-04 08:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moulinette", "0008_criterion_evaluator"),
    ]

    operations = [
        migrations.AddField(
            model_name="criterion",
            name="required_action",
            field=models.CharField(
                blank=True, max_length=256, verbose_name="Required action"
            ),
        ),
        migrations.AddField(
            model_name="criterion",
            name="required_action_stake",
            field=models.CharField(
                blank=True,
                choices=[("soumis", "Soumis"), ("interdit", "Interdit")],
                max_length=32,
                verbose_name="Required action stake",
            ),
        ),
    ]
