# Generated manually to add missing CharField lengths.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('historico', '0004_alter_navio_bordo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='navio',
            name='peso_descarga',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='navio',
            name='peso_embarque',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='navio',
            name='volume_descarga',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='navio',
            name='volume_embarque',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
