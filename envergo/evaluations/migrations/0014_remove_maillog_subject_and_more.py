# Generated by Django 4.2 on 2023-09-07 07:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0013_alter_maillog_subject"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="maillog",
            name="subject",
        ),
        migrations.AddField(
            model_name="regulatorynoticelog",
            name="last_clicked",
            field=models.DateTimeField(
                null=True, verbose_name="Last time the email was clicked"
            ),
        ),
        migrations.AddField(
            model_name="regulatorynoticelog",
            name="last_opened",
            field=models.DateTimeField(
                null=True, verbose_name="Last time the email was opened"
            ),
        ),
        migrations.AddField(
            model_name="regulatorynoticelog",
            name="nb_clicked",
            field=models.IntegerField(
                default=0, verbose_name="Number of times the email was clicked"
            ),
        ),
        migrations.AddField(
            model_name="regulatorynoticelog",
            name="nb_opened",
            field=models.IntegerField(
                default=0, verbose_name="Number of times the email was opened"
            ),
        ),
    ]
