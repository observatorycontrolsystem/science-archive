# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-06-01 16:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frames', '0003_frame_blkuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='frame',
            name='REQNUM',
            field=models.PositiveIntegerField(blank=True, db_index=True, help_text='Request id number, FITS header: REQNUM', null=True),
        ),
    ]
