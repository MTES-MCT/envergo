# Generated by Django 3.2.6 on 2021-11-09 08:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0010_auto_20211109_0856'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='zone',
            name='source_url',
        ),
    ]
