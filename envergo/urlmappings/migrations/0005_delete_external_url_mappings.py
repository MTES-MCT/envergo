"""Delete URL mappings pointing to external domains.

Before the domain whitelist was added to UrlMappingCreateForm, the shortener
accepted arbitrary URLs. Any existing mapping whose hostname is not one of our
own domains is spam and must be purged.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def delete_external_mappings(apps, schema_editor):
    UrlMapping = apps.get_model("urlmappings", "UrlMapping")
    allowed_domains = {
        settings.ENVERGO_AMENAGEMENT_DOMAIN,
        settings.ENVERGO_HAIE_DOMAIN,
    }
    to_delete = [
        mapping.pk
        for mapping in UrlMapping.objects.all()
        if urlparse(mapping.url).hostname not in allowed_domains
    ]
    UrlMapping.objects.filter(pk__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("urlmappings", "0004_add_contexte_to_moulinette_haie"),
    ]

    operations = [
        migrations.RunPython(delete_external_mappings, migrations.RunPython.noop),
    ]
