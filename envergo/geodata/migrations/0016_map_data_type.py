# Generated by Django 3.2.11 on 2022-01-24 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0015_alter_zone_map'),
    ]

    operations = [
        migrations.AddField(
            model_name='map',
            name='data_type',
            field=models.CharField(choices=[('zone_humide', 'Zone humide'), ('zone_inondable', 'Zone inondable')], default='zone_inondable', max_length=50, verbose_name='Data type'),
            preserve_default=False,
        ),
    ]
