from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.db import migrations


def add_contexte_non(apps, schema_editor):
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    Simulation = apps.get_model("petitions", "Simulation")
    UrlMapping = apps.get_model("urlmappings", "UrlMapping")

    def add_param(url):
        if not url:
            return url
        bits = urlsplit(url)
        query = parse_qs(bits.query)
        if "contexte" not in query or query["contexte"] == ["inconnu"]:
            query["contexte"] = ["non"]
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

    mappings_to_update = []
    for mapping in UrlMapping.objects.filter(url__contains="://haie.").filter(url__contains="element=").all():
        new_url = add_param(mapping.url)
        if new_url != mapping.url:
            mapping.url = new_url
            mappings_to_update.append(mapping)
    UrlMapping.objects.bulk_update(mappings_to_update, ["url"])


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0045_merge_20260311_1900"),
    ]

    operations = [
        migrations.RunPython(add_contexte_non, migrations.RunPython.noop),
    ]
