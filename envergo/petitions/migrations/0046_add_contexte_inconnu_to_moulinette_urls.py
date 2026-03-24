from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.db import migrations


def add_contexte_inconnu(apps, schema_editor):
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    Simulation = apps.get_model("petitions", "Simulation")

    def add_param(url):
        if not url:
            return url
        bits = urlsplit(url)
        query = parse_qs(bits.query)
        if "contexte" not in query:
            query["contexte"] = ["inconnu"]
            new_bits = bits._replace(query=urlencode(query, doseq=True))
            return urlunsplit(new_bits)
        return url

    projects_to_update = []
    for project in PetitionProject.objects.exclude(moulinette_url=""):
        new_url = add_param(project.moulinette_url)
        if new_url != project.moulinette_url:
            project.moulinette_url = new_url
            projects_to_update.append(project)
    PetitionProject.objects.bulk_update(projects_to_update, ["moulinette_url"])

    simulations_to_update = []
    for simulation in Simulation.objects.all():
        new_url = add_param(simulation.moulinette_url)
        if new_url != simulation.moulinette_url:
            simulation.moulinette_url = new_url
            simulations_to_update.append(simulation)
    Simulation.objects.bulk_update(simulations_to_update, ["moulinette_url"])


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0045_merge_20260311_1900"),
    ]

    operations = [
        migrations.RunPython(add_contexte_inconnu, migrations.RunPython.noop),
    ]
