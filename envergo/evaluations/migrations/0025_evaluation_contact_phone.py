# Generated by Django 4.2 on 2023-12-13 08:57

from django.db import migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0024_recipientstatus_reject_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="contact_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                max_length=20,
                region=None,
                verbose_name="Urbanism department phone number",
            ),
        ),
    ]
