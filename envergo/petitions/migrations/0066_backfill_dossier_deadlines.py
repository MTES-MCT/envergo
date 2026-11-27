from django.db import migrations

INSTRUCTION_STAGES = ("instruction_d", "instruction_a", "instruction_h")
PENDING_DECISION_STAGES = INSTRUCTION_STAGES + ("preparing_decision", "notification")


def backfill_dossier_deadlines(apps, schema_editor):
    """Copy the deadline in force onto each pending régime unique dossier."""
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    StatusLog = apps.get_model("petitions", "StatusLog")

    pending_projects = PetitionProject.objects.filter(
        _category="ru", stage__in=PENDING_DECISION_STAGES
    )

    updated = []
    for project in pending_projects:
        newest_first = StatusLog.objects.filter(petition_project=project).order_by(
            "-created_at"
        )
        latest_instruction_stage = (
            newest_first.filter(stage__in=INSTRUCTION_STAGES)
            .values_list("stage", flat=True)
            .first()
        )

        # The silence rule in force follows the latest instruction stage.
        if latest_instruction_stage == "instruction_d":
            project.agreement_deadline = (
                newest_first.filter(agreement_deadline__isnull=False)
                .values_list("agreement_deadline", flat=True)
                .first()
            )
            updated.append(project)
        elif latest_instruction_stage == "instruction_a":
            project.refusal_deadline = (
                newest_first.filter(refusal_deadline__isnull=False)
                .values_list("refusal_deadline", flat=True)
                .first()
            )
            updated.append(project)

    PetitionProject.objects.bulk_update(
        updated, ["agreement_deadline", "refusal_deadline"]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0065_dossier_deadlines"),
    ]

    operations = [
        migrations.RunPython(backfill_dossier_deadlines, migrations.RunPython.noop),
    ]
