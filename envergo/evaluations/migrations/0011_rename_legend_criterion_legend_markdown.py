# Generated by Django 3.2.6 on 2021-08-24 09:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0010_auto_20210823_1232'),
    ]

    operations = [
        migrations.RenameField(
            model_name='criterion',
            old_name='legend',
            new_name='legend_md',
        ),
    ]
