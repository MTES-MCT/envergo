# Generated by Django 3.2.12 on 2022-05-17 08:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0063_merge_20220509_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='user_type',
            field=models.CharField(choices=[('instructor', 'Un service instruction urbanisme'), ('petitioner', "Un porteur de projet ou maître d'œuvre")], default='instructor', max_length=32, verbose_name='Who are you?'),
            preserve_default=False,
        ),
    ]
