from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0068_backfill_dossier_silence_rule"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="petitionproject",
            name="agreement_deadline",
        ),
        migrations.RemoveField(
            model_name="petitionproject",
            name="refusal_deadline",
        ),
    ]
