# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-10-04 16:05
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0016_value__type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='collection',
            options={'permissions': (('view_resource', 'View resource'), ('change_authorizations', 'Change authorizations'), ('view_authorizations', 'View authorizations'))},
        ),
        migrations.AlterModelOptions(
            name='resource',
            options={'permissions': (('view_resource', 'View resource'), ('change_authorizations', 'Change authorizations'), ('view_authorizations', 'View authorizations'))},
        ),
    ]