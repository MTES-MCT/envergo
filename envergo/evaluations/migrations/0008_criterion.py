# Generated by Django 3.2.6 on 2021-08-23 09:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0007_auto_20210816_1212'),
    ]

    operations = [
        migrations.CreateModel(
            name='Criterion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Order')),
                ('probability', models.IntegerField(choices=[(1, 'Unlikely'), (2, 'Possible'), (3, 'Likely'), (4, 'Very likely')], verbose_name='Probability')),
                ('criterion', models.CharField(choices=[('rainwater_runoff', 'Rainwater runoff'), ('flood_zone', 'Flood zone'), ('wetland', 'Wetland')], max_length=128, verbose_name='Criterion')),
                ('description_md', models.TextField(verbose_name='Description')),
                ('description_html', models.TextField(verbose_name='Description (html)')),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='evaluations.evaluation', verbose_name='Evaluation')),
            ],
            options={
                'verbose_name': 'Criterion',
                'verbose_name_plural': 'Criterions',
            },
        ),
    ]
