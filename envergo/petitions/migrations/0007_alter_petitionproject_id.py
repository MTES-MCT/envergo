# Generated by Django 4.2.19 on 2025-04-07 09:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0006_petitionproject_demarches_simplifiees_date_depot_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="petitionproject",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
