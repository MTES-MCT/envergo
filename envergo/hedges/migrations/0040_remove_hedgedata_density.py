from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hedges", "0039_drop_legacy_density_cache"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="hedgedata",
            name="_density",
        ),
    ]
