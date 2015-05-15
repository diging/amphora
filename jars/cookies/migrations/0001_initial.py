# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import cookies.models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('concepts', '__first__'),
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
        ),
        migrations.CreateModel(
            name='Authorization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('actor', models.ForeignKey(related_name='is_authorized_to', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Entity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Names are unique accross ALL entities in the system.', max_length=255)),
                ('hidden', models.BooleanField(default=False, help_text=b'If a resource is hidden it will not appear in search results and will not be accessible directly, even for logged-in users.')),
                ('public', models.BooleanField(default=True, help_text=b'If a resource is not public it will only be accessible to logged-in users and will not appear in public search results.')),
                ('namespace', models.CharField(max_length=255, null=True, blank=True)),
                ('uri', models.CharField(help_text=b'You may provide your own URI, or allow the system to assign one automatically (recommended).', max_length=255, null=True, verbose_name=b'URI', blank=True)),
            ],
            options={
                'verbose_name_plural': 'entities',
            },
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('when', models.DateTimeField(auto_now_add=True)),
                ('by', models.ForeignKey(related_name='events', to=settings.AUTH_USER_MODEL)),
                ('did', models.ForeignKey(related_name='events', to='cookies.Action')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Schema',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('namespace', models.CharField(max_length=255, null=True, blank=True)),
                ('uri', models.CharField(max_length=255, null=True, verbose_name=b'URI', blank=True)),
                ('active', models.BooleanField(default=True)),
                ('real_type', models.ForeignKey(editable=False, to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('namespace', models.CharField(max_length=255, null=True, blank=True)),
                ('uri', models.CharField(max_length=255, null=True, verbose_name=b'URI', blank=True)),
                ('description', models.TextField(null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConceptEntity',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
                ('concept', models.ForeignKey(to='concepts.Concept')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='ConceptType',
            fields=[
                ('type_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Type')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.type',),
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
            name='Relation',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
                ('predicate', models.ForeignKey(related_name='instances', verbose_name=b'field', to='cookies.Field')),
            ],
            options={
                'verbose_name': 'metadata relation',
            },
            bases=('cookies.entity',),
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('entity_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Entity')),
                ('indexable_content', models.TextField(null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.entity',),
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
        migrations.AddField(
            model_name='type',
            name='domain',
            field=models.ManyToManyField(help_text=b'The domain specifies the resource types to which this Type or Field can apply. If no domain is specified, then this Type or Field can apply to any resource.', related_name='in_domain_of', null=True, to='cookies.Type', blank=True),
        ),
        migrations.AddField(
            model_name='type',
            name='parent',
            field=models.ForeignKey(related_name='children', blank=True, to='cookies.Type', null=True),
        ),
        migrations.AddField(
            model_name='type',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='type',
            name='schema',
            field=models.ForeignKey(related_name='types', blank=True, to='cookies.Schema', null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='on',
            field=models.ForeignKey(related_name='events', to='cookies.Entity'),
        ),
        migrations.AddField(
            model_name='event',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='entity',
            name='entity_type',
            field=models.ForeignKey(blank=True, to='cookies.Type', help_text=b'Specifying a type helps to determine what metadata fields are appropriate for this resource, and can help with searching. Note that type-specific filtering of metadata fields will only take place after this resource has been saved.', null=True, verbose_name=b'type'),
        ),
        migrations.AddField(
            model_name='entity',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='authorization',
            name='on',
            field=models.ForeignKey(to='cookies.Entity'),
        ),
        migrations.AddField(
            model_name='authorization',
            name='real_type',
            field=models.ForeignKey(editable=False, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='authorization',
            name='to_do',
            field=models.ForeignKey(related_name='authorizations', to='cookies.Action'),
        ),
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('resource_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Resource')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.resource',),
        ),
        migrations.CreateModel(
            name='DateTimeValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('_value', models.DateTimeField(unique=True, null=True, blank=True)),
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
                ('_value', models.FloatField(unique=True)),
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
                ('_value', models.IntegerField(default=0, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.CreateModel(
            name='LocalResource',
            fields=[
                ('resource_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Resource')),
                ('file', models.FileField(help_text=b'Drop a file onto this field, or click "Choose File" to select a file on your computer.', null=True, upload_to=cookies.models.resource_file_name, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.resource', models.Model),
        ),
        migrations.CreateModel(
            name='RemoteResource',
            fields=[
                ('resource_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Resource')),
                ('location', models.URLField(max_length=255, verbose_name=b'URL')),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.resource', models.Model),
        ),
        migrations.CreateModel(
            name='StringValue',
            fields=[
                ('value_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cookies.Value')),
                ('_value', models.TextField()),
            ],
            options={
                'abstract': False,
            },
            bases=('cookies.value',),
        ),
        migrations.AddField(
            model_name='relation',
            name='source',
            field=models.ForeignKey(related_name='relations_from', to='cookies.Entity'),
        ),
        migrations.AddField(
            model_name='relation',
            name='target',
            field=models.ForeignKey(related_name='relations_to', verbose_name=b'value', to='cookies.Entity'),
        ),
        migrations.AddField(
            model_name='field',
            name='range',
            field=models.ManyToManyField(help_text=b"The field's range specifies the resource types that are valid values for this field. If no range is specified, then this field will accept any value.", related_name='in_range_of', null=True, to='cookies.Type', blank=True),
        ),
        migrations.AddField(
            model_name='concepttype',
            name='type_concept',
            field=models.ForeignKey(to='concepts.Type'),
        ),
        migrations.AddField(
            model_name='collection',
            name='resources',
            field=models.ManyToManyField(related_name='part_of', null=True, to='cookies.Resource', blank=True),
        ),
    ]
