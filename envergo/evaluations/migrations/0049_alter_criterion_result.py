# Generated by Django 3.2.11 on 2022-01-14 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0048_set_evaluations_results'),
    ]

    operations = [
        migrations.AlterField(
            model_name='criterion',
            name='result',
            field=models.IntegerField(choices=[(1, 'Subject to LSE'), (2, 'Non subject to LSE'), (3, 'Action required')], default=2, verbose_name='Result'),
            preserve_default=False,
        ),
    ]
