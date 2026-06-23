"""Add urgence=non to moulinette URLs that would trigger the emergency question.

The new RegimeUniqueHaieForm requires an `urgence` answer when:
- the department has single_procedure=True (régime unique)
- the motif is in ("securite", "chemin_acces", "autre")

Without this param, existing URLs become invalid — the moulinette redirects
to the form, and instruction pages show "non disponible" instead of the
real result.
"""

from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.db import migrations

URGENCE_MOTIFS = ("securite", "chemin_acces", "autre")


def add_urgence_non(apps, schema_editor):
    """Backfill urgence=non on URLs that need it."""

    ConfigHaie = apps.get_model("moulinette", "ConfigHaie")
    PetitionProject = apps.get_model("petitions", "PetitionProject")
    Simulation = apps.get_model("petitions", "Simulation")

    # A department can have multiple ConfigHaie objects with different
    # validity ranges — some in droit constant, some in régime unique.
    # We collect departments that have ANY RU config. This is intentionally
    # broad: adding urgence=non to a URL whose date falls in a DC period is
    # harmless (the form has no fields, the param is ignored), but missing a
    # URL whose date falls in an RU period would break instruction pages.
    ru_depts = set(
        ConfigHaie.objects.filter(single_procedure=True).values_list(
            "department__department", flat=True
        )
    )
    if not ru_depts:
        return

    def needs_urgence(url):
        """Return True if the URL matches trigger conditions and lacks urgence."""
        if not url:
            return False
        query = parse_qs(urlsplit(url).query)
        if "urgence" in query:
            return False
        dept = query.get("department", [None])[0]
        motif = query.get("motif", [None])[0]
        return dept in ru_depts and motif in URGENCE_MOTIFS

    def add_param(url):
        bits = urlsplit(url)
        query = parse_qs(bits.query)
        query["urgence"] = ["non"]
        new_bits = bits._replace(query=urlencode(query, doseq=True))
        return urlunsplit(new_bits)

    projects_to_update = []
    for project in PetitionProject.objects.exclude(moulinette_url=""):
        if needs_urgence(project.moulinette_url):
            project.moulinette_url = add_param(project.moulinette_url)
            projects_to_update.append(project)
    if projects_to_update:
        PetitionProject.objects.bulk_update(projects_to_update, ["moulinette_url"])

    simulations_to_update = []
    for simulation in Simulation.objects.all():
        if needs_urgence(simulation.moulinette_url):
            simulation.moulinette_url = add_param(simulation.moulinette_url)
            simulations_to_update.append(simulation)
    if simulations_to_update:
        Simulation.objects.bulk_update(simulations_to_update, ["moulinette_url"])


class Migration(migrations.Migration):

    dependencies = [
        ("petitions", "0048_alter_statuslog_update_comment"),
        ("moulinette", "0128_alter_moulinettetemplate_key"),
    ]

    operations = [
        migrations.RunPython(add_urgence_non, migrations.RunPython.noop),
    ]
