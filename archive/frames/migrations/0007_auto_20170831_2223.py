# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-08-31 22:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frames', '0006_auto_20170817_1823'),
    ]

    operations = [
        migrations.AlterField(
            model_name='frame',
            name='OBSTYPE',
            field=models.CharField(choices=[('BIAS', 'BIAS'), ('DARK', 'DARK'), ('EXPERIMENTAL', 'EXPERIMENTAL'), ('EXPOSE', 'EXPOSE'), ('SKYFLAT', 'SKYFLAT'), ('STANDARD', 'STANDARD'), ('TRAILED', 'TRAILED'), ('GUIDE', 'GUIDE'), ('SPECTRUM', 'SPECTRUM'), ('ARC', 'ARC'), ('LAMPFLAT', 'LAMPFLAT'), ('CATALOG', 'CATALOG'), ('BPM', 'BPM'), ('TARGET', 'TARGET'), ('TEMPLATE', 'TEMPLATE'), ('OBJECT', 'OBJECT'), ('TRACE', 'TRACE'), ('DOUBLE', 'DOUBLE')], default='', help_text='Type of observation. FITS header: OBSTYPE', max_length=20),
        ),
    ]
