from dateutil.relativedelta import relativedelta
from django.db import migrations

DECLARATION_DELAY = relativedelta(months=2)


def backfill_declaration_entry_deadline(apps, schema_editor):
    """Start the agreement delay on each past entry of a régime unique dossier into déclaration."""
    StatusLog = apps.get_model("petitions", "StatusLog")

    history = StatusLog.objects.filter(petition_project___category="ru").order_by(
        "petition_project_id", "created_at"
    )

    # Every log type carries the dossier's stage. The previous log holds the stage it left.
    entries = []
    previous_stage_by_project = {}
    for log in history:
        previous_stage = previous_stage_by_project.get(log.petition_project_id)
        enters_declaration = (
            log.type == "status_change"
            and log.stage == "instruction_d"
            and previous_stage != "instruction_d"
        )
        if enters_declaration and log.agreement_deadline is None:
            log.agreement_deadline = log.status_date + DECLARATION_DELAY
            entries.append(log)
        previous_stage_by_project[log.petition_project_id] = log.stage

    StatusLog.objects.bulk_update(entries, ["agreement_deadline"])


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0063_backfill_agreement_deadline"),
    ]

    operations = [
        migrations.RunPython(
            backfill_declaration_entry_deadline, migrations.RunPython.noop
        ),
    ]
