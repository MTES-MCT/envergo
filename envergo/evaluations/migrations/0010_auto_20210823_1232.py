# Generated by Django 3.2.6 on 2021-08-23 12:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0009_alter_criterion_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='criterion',
            name='legend',
            field=models.CharField(blank=True, max_length=256, verbose_name='Legend'),
        ),
        migrations.AddField(
            model_name='criterion',
            name='map',
            field=models.ImageField(blank=True, null=True, upload_to='', verbose_name='Map'),
        ),
        migrations.AlterField(
            model_name='criterion',
            name='criterion',
            field=models.CharField(choices=[('rainwater_runoff', 'Capture of more than 1 ha of rainwater runoff'), ('flood_zone', 'Building of more than 400\xa0m¹ in a flood zone'), ('wetland', 'More than 1000\xa0m² impact on wetlands')], max_length=128, verbose_name='Criterion'),
        ),
        migrations.AlterField(
            model_name='criterion',
            name='evaluation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='criterions', to='evaluations.evaluation', verbose_name='Evaluation'),
        ),
    ]
