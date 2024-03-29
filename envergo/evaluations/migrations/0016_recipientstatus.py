# Generated by Django 4.2 on 2023-09-08 08:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0015_remove_regulatorynoticelog_last_clicked_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecipientStatus",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "recipient",
                    models.EmailField(max_length=254, verbose_name="Recipient"),
                ),
                ("status", models.CharField(max_length=64, verbose_name="Status")),
                ("latest_status", models.DateTimeField(verbose_name="Latest status")),
                ("nb_opened", models.IntegerField(default=0, verbose_name="Nb opened")),
                (
                    "latest_opened",
                    models.DateTimeField(null=True, verbose_name="Latest opened"),
                ),
                (
                    "nb_clicked",
                    models.IntegerField(default=0, verbose_name="Nb clicked"),
                ),
                (
                    "latest_clicked",
                    models.DateTimeField(null=True, verbose_name="Latest clicked"),
                ),
                (
                    "regulatory_notice_log",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipient_statuses",
                        to="evaluations.regulatorynoticelog",
                    ),
                ),
            ],
            options={
                "verbose_name": "Recipient status",
                "verbose_name_plural": "Recipient statuses",
            },
        ),
    ]
