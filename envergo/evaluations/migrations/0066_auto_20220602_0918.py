# Generated by Django 3.2.12 on 2022-06-02 09:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0065_auto_20220525_1004'),
    ]

    operations = [
        migrations.AlterField(
            model_name='criterion',
            name='result',
            field=models.CharField(choices=[('soumis', 'Seuil franchi'), ('non_soumis', 'Seuil non franchi'), ('action_requise', 'Action requise'), ('non_applicable', 'Non concernĂ©')], max_length=32, verbose_name='Result'),
        ),
        migrations.AlterField(
            model_name='evaluation',
            name='result',
            field=models.CharField(choices=[('soumis', 'Soumis'), ('non_soumis', 'Non soumis'), ('action_requise', 'Action requise'), ('non_disponible', 'Non disponible'), ('non_applicable', 'Non concernĂ©')], max_length=32, null=True, verbose_name='Result'),
        ),
        migrations.AlterField(
            model_name='request',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='E-mail'),
        ),
    ]
