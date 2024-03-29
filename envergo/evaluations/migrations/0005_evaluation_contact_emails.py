# Generated by Django 4.2 on 2023-08-22 07:37

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0004_request_contact_emails_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="contact_emails",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                default=list,
                size=None,
                verbose_name="Contact e-mails",
            ),
            preserve_default=False,
        ),
    ]
