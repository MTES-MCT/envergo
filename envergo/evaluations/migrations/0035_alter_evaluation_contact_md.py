# Generated by Django 3.2.6 on 2021-10-25 12:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0034_alter_evaluation_request'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evaluation',
            name='contact_md',
            field=models.TextField(verbose_name='Contact'),
        ),
    ]
