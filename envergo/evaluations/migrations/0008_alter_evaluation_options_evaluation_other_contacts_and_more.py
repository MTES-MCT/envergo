# Generated by Django 4.2 on 2023-09-15 12:27

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import phonenumber_field.modelfields


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0007_remove_evaluation_contact_email_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="evaluation",
            options={"verbose_name": "Avis", "verbose_name_plural": "Avis"},
        ),
        migrations.AddField(
            model_name="evaluation",
            name="other_contacts",
            field=models.TextField(blank=True, verbose_name="Other contacts"),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="project_description",
            field=models.TextField(
                blank=True, verbose_name="Project description, comments"
            ),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="project_sponsor_emails",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                blank=True,
                default=list,
                size=None,
                verbose_name="Project sponsor email(s)",
            ),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="project_sponsor_phone_number",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                max_length=20,
                region=None,
                verbose_name="Project sponsor phone number",
            ),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="send_eval_to_sponsor",
            field=models.BooleanField(
                default=True, verbose_name="Send evaluation to project sponsor"
            ),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="user_type",
            field=models.CharField(
                choices=[
                    ("instructor", "Un service instruction urbanisme"),
                    ("petitioner", "Un porteur de projet ou maître d'œuvre"),
                ],
                default="instructor",
                max_length=32,
                verbose_name="Who are you?",
            ),
        ),
        migrations.AlterField(
            model_name="evaluation",
            name="contact_emails",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                blank=True,
                default=list,
                size=None,
                verbose_name="Urbanism department email address(es)",
            ),
        ),
        migrations.AlterField(
            model_name="evaluation",
            name="details_md",
            field=models.TextField(
                blank=True,
                help_text="Will be included in the notice page.\n            Only simple markdown (*bold*, _italic_, [links](https://url), newlines).",
                verbose_name="Additional mention",
            ),
        ),
        migrations.AlterField(
            model_name="evaluation",
            name="request",
            field=models.OneToOneField(
                blank=True,
                help_text="Does this regulatory notice answers to an existing request?",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="evaluations.request",
                verbose_name="Demande associée",
            ),
        ),
        migrations.AlterField(
            model_name="evaluation",
            name="rr_mention_md",
            field=models.TextField(
                blank=True,
                help_text="Will be included in the RR email.\n            Only simple markdown (*bold*, _italic_, [links](https://url), newlines).",
                verbose_name="Regulatory reminder mention",
            ),
        ),
        migrations.AlterField(
            model_name="request",
            name="contact_emails",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                blank=True,
                default=list,
                size=None,
                verbose_name="Urbanism department email address(es)",
            ),
        ),
    ]
