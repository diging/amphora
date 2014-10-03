# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0004_auto_20141003_1611'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resource',
            name='part_of',
        ),
        migrations.AddField(
            model_name='collection',
            name='resources',
            field=models.ManyToManyField(related_name=b'part_of', null=True, to='cookies.Resource', blank=True),
            preserve_default=True,
        ),
    ]
