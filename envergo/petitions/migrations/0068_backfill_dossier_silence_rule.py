from django.db import migrations

INSTRUCTION_STAGES = ("instruction_d", "instruction_a", "instruction_h")
PENDING_DECISION_STAGES = INSTRUCTION_STAGES + ("preparing_decision", "notification")

# The silence rule of each instruction stage, and the dossier field holding its deadline.
SILENCE_BY_STAGE = {
    "instruction_d": ("agreement", "agreement_deadline"),
    "instruction_a": ("refusal", "refusal_deadline"),
}


def backfill_dossier_silence_rule(apps, schema_editor):
    """Store the silence rule in force and its deadline on each pending régime unique dossier."""
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    StatusLog = apps.get_model("petitions", "StatusLog")

    pending_projects = PetitionProject.objects.filter(
        _category="ru", stage__in=PENDING_DECISION_STAGES
    )

    updated = []
    for project in pending_projects:
        latest_instruction_stage = (
            StatusLog.objects.filter(
                petition_project=project, stage__in=INSTRUCTION_STAGES
            )
            .order_by("-created_at")
            .values_list("stage", flat=True)
            .first()
        )

        # The silence rule in force follows the latest instruction stage.
        silence = SILENCE_BY_STAGE.get(latest_instruction_stage)
        if silence:
            rule, deadline_field = silence
            project.silence_rule = rule
            project.silence_deadline = getattr(project, deadline_field)
            updated.append(project)

    PetitionProject.objects.bulk_update(updated, ["silence_rule", "silence_deadline"])


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0067_dossier_silence_rule"),
    ]

    operations = [
        migrations.RunPython(backfill_dossier_silence_rule, migrations.RunPython.noop),
    ]
