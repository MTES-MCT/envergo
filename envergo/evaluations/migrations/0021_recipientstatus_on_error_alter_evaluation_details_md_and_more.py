# Generated by Django 4.2 on 2023-11-30 08:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0020_alter_evaluation_notice_log_cascade"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipientstatus",
            name="on_error",
            field=models.BooleanField(default=False, verbose_name="On error"),
        ),
    ]
