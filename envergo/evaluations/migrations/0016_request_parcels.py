# Generated by Django 3.2.6 on 2021-08-26 14:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0001_initial'),
        ('evaluations', '0015_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='parcels',
            field=models.ManyToManyField(to='geodata.Parcel', verbose_name='Parcels'),
        ),
    ]
