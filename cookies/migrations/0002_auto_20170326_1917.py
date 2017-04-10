# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-03-26 19:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='relation',
            options={'ordering': ['id'], 'permissions': (('view_relation', 'View relation'), ('change_authorizations', 'Change authorizations'), ('view_authorizations', 'View authorizations')), 'verbose_name': 'metadata relation'},
        ),
        migrations.AlterField(
            model_name='conceptentity',
            name='concept',
            field=models.ManyToManyField(blank=True, to='concepts.Concept'),
        ),
        migrations.AlterField(
            model_name='field',
            name='domain',
            field=models.ManyToManyField(blank=True, help_text=b'The domain specifies the resource types to which this Type or Field can apply. If no domain is specified, then this Type or Field can apply to any resource.', to='cookies.Type'),
        ),
        migrations.AlterField(
            model_name='field',
            name='range',
            field=models.ManyToManyField(blank=True, help_text=b"The field's range specifies the resource types that are valid values for this field. If no range is specified, then this field will accept any value.", related_name='in_range_of', to='cookies.Type'),
        ),
        migrations.AlterField(
            model_name='type',
            name='domain',
            field=models.ManyToManyField(blank=True, help_text=b'The domain specifies the resource types to which this Type or Field can apply. If no domain is specified, then this Type or Field can apply to any resource.', to='cookies.Type'),
        ),
    ]
