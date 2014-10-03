# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0005_auto_20141003_1616'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='collection',
            name='resources',
        ),
        migrations.AddField(
            model_name='resource',
            name='part_of',
            field=models.ManyToManyField(related_name=b'contains', null=True, to='cookies.Collection', blank=True),
            preserve_default=True,
        ),
    ]
