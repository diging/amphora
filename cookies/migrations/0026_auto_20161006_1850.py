# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-10-06 18:50
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0025_auto_20161006_1848'),
    ]

    operations = [
        migrations.AddField(
            model_name='gilessession',
            name='updated',
            field=models.DateTimeField(auto_now=True, default=datetime.datetime(2016, 10, 6, 18, 50, 35, 954554)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='gilesupload',
            name='updated',
            field=models.DateTimeField(auto_now=True, default=datetime.datetime(2016, 10, 6, 18, 50, 46, 251051)),
            preserve_default=False,
        ),
    ]