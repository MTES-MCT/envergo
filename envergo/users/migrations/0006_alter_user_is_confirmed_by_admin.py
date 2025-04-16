# Generated by Django 4.2.19 on 2025-04-07 09:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_alter_user_access_amenagement"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="is_confirmed_by_admin",
            field=models.BooleanField(
                default=False,
                help_text="Uniquement pour l'accès au GuH",
                verbose_name="Confirmed by an admin",
            ),
        ),
    ]
