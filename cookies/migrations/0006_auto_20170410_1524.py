# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-04-10 15:24
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cookies', '0005_resource_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resourceauthorization',
            name='granted_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='resource_collection_auths', to=settings.AUTH_USER_MODEL),
        ),
    ]