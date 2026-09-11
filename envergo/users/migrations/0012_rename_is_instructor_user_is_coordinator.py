from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_rename_is_instructor_for_departments_user_is_instructor"),
    ]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="is_instructor",
            new_name="is_coordinator",
        ),
        migrations.AlterField(
            model_name="user",
            name="is_coordinator",
            field=models.BooleanField(
                default=False,
                help_text="""Donne les droits de coordonnateur sur tous les dossiers des départements autorisés pour ce user.
        Si cette case n'est pas cochée, la personne a le statut d'instructeur consulté ou d'invitée.""",
                verbose_name="Coordonnateur GUH d'un ou plusieurs départements",
            ),
        ),
    ]
