# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import cookies.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(unique=True, max_length=2, choices=[(b'GR', b'GRANT'), (b'DL', b'DELETE'), (b'CH', b'CHANGE'), (b'VW', b'VIEW')])),
                ('real_type', models.ForeignKey(editable=False, to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Authorization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('actor', models.ForeignKey(related_name=b'is_authorized_to', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Entity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=500)),
            ],
            options={
                'verbose_name_plural': 'entities',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('when', models.DateTimeField(auto_now_add=True)),
                ('by', models.ForeignKey(related_name=b'events', to=settings.AUTH_USER_MODEL)),
                ('did', models.ForeignKey(related_name=b'events', to='cookies.Action')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Relation',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='RemoteResource',
            fields=[
                ('resource_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Resource')),
                ('url', models.URLField(max_length=2000)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.resource', models.Model),
        ),
        migrations.CreateModel(
            name='LocalResource',
            fields=[
                ('resource_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Resource')),
                ('file', models.FileField(null=True, upload_to=cookies.models.resource_file_name, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.resource', models.Model),
        ),
        migrations.CreateModel(
            name='Schema',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='Field',
            fields=[
                ('type_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Type')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.type',),
        ),
        migrations.CreateModel(
            name='Value',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='StringValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('name', models.TextField(unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.CreateModel(
            name='IntegerValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('name', models.IntegerField(default=0, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.CreateModel(
            name='FloatValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('name', models.FloatField(unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.CreateModel(
            name='DateTimeValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('name', models.DateTimeField(unique=True, null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.AddField(
            model_name='type',
            name='domain',
            field=models.ManyToManyField(related_name=b'in_domain_of', null=True, to='cookies.Type', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='type',
            name='parent',
            field=models.ForeignKey(related_name=b'children', blank=True, to='cookies.Type', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='type',
            name='schema',
            field=models.ForeignKey(related_name=b'types', blank=True, to='cookies.Schema', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='relation',
            name='predicate',
            field=models.ForeignKey(related_name=b'instances', to='cookies.Field'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='relation',
            name='source',
            field=models.ForeignKey(related_name=b'relations_from', to='cookies.Entity'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='relation',
            name='target',
            field=models.ForeignKey(related_name=b'relations_to', to='cookies.Entity'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='field',
            name='range',
            field=models.ManyToManyField(related_name=b'in_range_of', null=True, to='cookies.Type', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='event',
            name='on',
            field=models.ForeignKey(related_name=b'events', to='cookies.Entity'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='event',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='entity',
            name='entity_type',
            field=models.ForeignKey(blank=True, to='cookies.Type', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='entity',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collection',
            name='resources',
            field=models.ManyToManyField(related_name=b'part_of', null=True, to='cookies.Resource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='authorization',
            name='on',
            field=models.ForeignKey(to='cookies.Entity'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='authorization',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='authorization',
            name='to_do',
            field=models.ForeignKey(related_name=b'authorizations', to='cookies.Action'),
            preserve_default=True,
        ),
    ]
