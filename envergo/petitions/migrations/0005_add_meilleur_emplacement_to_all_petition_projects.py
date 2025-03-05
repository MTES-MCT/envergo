from django.db import migrations, transaction
from django.db.models import F
from tqdm import tqdm


@transaction.atomic
def set_meilleur_emplacement(apps, schema_editor):
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    qs = PetitionProject.objects.exclude(moulinette_url__icontains='meilleur_emplacement')
    total = qs.count()
    batch_size = 1000
    i = 0
    with tqdm(total=total) as pbar:
        while i < total:
            models = qs[i: i + batch_size].iterator()  # noqa
            to_update = []
            for model in models:
                model.moulinette_url = f"{model.moulinette_url}&meilleur_emplacement=non"
                to_update.append(model)

            PetitionProject.objects.bulk_update(to_update, ["moulinette_url"])
            i += batch_size
            pbar.update(batch_size)


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0004_petitionproject_instructor_free_mention_and_more"),
    ]

    operations = [
        migrations.RunPython(set_meilleur_emplacement, migrations.RunPython.noop),
    ]
