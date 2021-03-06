# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-29 18:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frames', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='frame',
            name='OBSTYPE',
            field=models.CharField(choices=[('BIAS', 'BIAS'), ('DARK', 'DARK'), ('EXPERIMENTAL', 'EXPERIMENTAL'), ('EXPOSE', 'EXPOSE'), ('SKYFLAT', 'SKYFLAT'), ('STANDARD', 'STANDARD'), ('TRAILED', 'TRAILED'), ('GUIDE', 'GUIDE'), ('SPECTRUM', 'SPECTRUM'), ('ARC', 'ARC'), ('LAMPFLAT', 'LAMPFLAT'), ('CATALOG', 'CATALOG')], default='', help_text='Type of observation. FITS header: OBSTYPE', max_length=20),
        ),
    ]
