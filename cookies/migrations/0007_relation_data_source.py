# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-04-11 17:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0006_auto_20170410_1524'),
    ]

    operations = [
        migrations.AddField(
            model_name='relation',
            name='data_source',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
