# Generated by Django 3.2.11 on 2022-01-14 12:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0050_alter_criterion_probability'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='evaluation',
            name='global_probability',
        ),
    ]
