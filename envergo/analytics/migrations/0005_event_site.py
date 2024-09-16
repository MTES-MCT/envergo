# Generated by Django 4.2.13 on 2024-09-05 04:28

from django.db import migrations, models, transaction
import django.db.models.deletion
from django.db.models import Q
from tqdm import tqdm


@transaction.atomic
def set_haie_site(apps, schema_editor):
    Event = apps.get_model("analytics", "Event")
    qs = Event.objects.filter(Q(metadata__has_key='url') & Q(metadata__url__icontains='://haie.'))
    total = qs.count()
    batch_size = 1000
    i = 0
    with tqdm(total=total) as pbar:
        while i < total:
            models = qs[i: i + batch_size].iterator()  # noqa
            to_update = []
            for model in models:
                model.site_id = 2
                to_update.append(model)

            Event.objects.bulk_update(to_update, ["site_id"])
            i += batch_size
            pbar.update(batch_size)


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0002_add_haie"),
        ("analytics", "0004_update_reference_field_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="site",
            field=models.ForeignKey(
                default=1, on_delete=django.db.models.deletion.PROTECT, to="sites.site"
            ),
        ),
        migrations.RunPython(set_haie_site, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="sites.site"
            ),
        ),
    ]