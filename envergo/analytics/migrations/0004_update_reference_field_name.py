# Generated by Django 4.2 on 2024-03-29 10:33

from django.db import migrations


def update_reference_field_name(apps, schema_editor):
    Event = apps.get_model("analytics", "Event")
    events = Event.objects.filter(metadata__has_key="reference")
    for event in events:
        event.metadata["request_reference"] = event.metadata.pop("reference")
        event.save()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0003_alter_event_session_key"),
    ]

    operations = [
        migrations.RunPython(update_reference_field_name, migrations.RunPython.noop)
    ]
