# Generated by Django 3.2.16 on 2023-04-11 07:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0036_auto_20230411_0752'),
    ]

    operations = [
        migrations.RenameField(
            model_name='map',
            old_name='data_certainty',
            new_name='data_type',
        ),
    ]
