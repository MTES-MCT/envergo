from django.db import migrations


def migrate_category_values(apps, schema_editor):
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    mapping = {
        "Régime unique": "ru",
        "L350-3": "l350_3",
        "Hors régime unique": "hru",
    }
    for old_value, new_value in mapping.items():
        PetitionProject.objects.filter(_category=old_value).update(_category=new_value)


def reverse_category_values(apps, schema_editor):
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    mapping = {
        "ru": "Régime unique",
        "l350_3": "L350-3",
        "hru": "Hors régime unique",
    }
    for old_value, new_value in mapping.items():
        PetitionProject.objects.filter(_category=old_value).update(_category=new_value)


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0050_petitionproject_original_multi_category_moulinette_url"),
    ]

    operations = [
        migrations.RunPython(migrate_category_values, reverse_category_values),
    ]
