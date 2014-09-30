# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Authority'
        db.create_table(u'cookies_authority', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('endpoint', self.gf('django.db.models.fields.TextField')()),
            ('namespace', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'cookies', ['Authority'])

        # Adding model 'Entity'
        db.create_table(u'cookies_entity', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
        ))
        db.send_create_signal(u'cookies', ['Entity'])

        # Adding model 'Resource'
        db.create_table(u'cookies_resource', (
            (u'entity_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Entity'], unique=True, primary_key=True)),
            ('description', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'cookies', ['Resource'])

        # Adding model 'RemoteResource'
        db.create_table(u'cookies_remoteresource', (
            (u'resource_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Resource'], unique=True, primary_key=True)),
            ('url', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'cookies', ['RemoteResource'])

        # Adding model 'LocalResource'
        db.create_table(u'cookies_localresource', (
            (u'resource_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Resource'], unique=True, primary_key=True)),
            ('file', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal(u'cookies', ['LocalResource'])

        # Adding model 'Corpus'
        db.create_table(u'cookies_corpus', (
            (u'resource_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Resource'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Corpus'])

        # Adding model 'Schema'
        db.create_table(u'cookies_schema', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Schema'])

        # Adding M2M table for field fields on 'Schema'
        m2m_table_name = db.shorten_name(u'cookies_schema_fields')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('schema', models.ForeignKey(orm[u'cookies.schema'], null=False)),
            ('field', models.ForeignKey(orm[u'cookies.field'], null=False))
        ))
        db.create_unique(m2m_table_name, ['schema_id', 'field_id'])

        # Adding model 'Field'
        db.create_table(u'cookies_field', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=2)),
        ))
        db.send_create_signal(u'cookies', ['Field'])

        # Adding model 'FieldRelation'
        db.create_table(u'cookies_fieldrelation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='relations_from', to=orm['cookies.Entity'])),
            ('field', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['cookies.Field'])),
        ))
        db.send_create_signal(u'cookies', ['FieldRelation'])

        # Adding model 'ValueRelation'
        db.create_table(u'cookies_valuerelation', (
            (u'fieldrelation_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.FieldRelation'], unique=True, primary_key=True)),
            ('value', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['cookies.Value'])),
        ))
        db.send_create_signal(u'cookies', ['ValueRelation'])

        # Adding model 'EntityRelation'
        db.create_table(u'cookies_entityrelation', (
            (u'fieldrelation_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.FieldRelation'], unique=True, primary_key=True)),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='relations_to', to=orm['cookies.Entity'])),
        ))
        db.send_create_signal(u'cookies', ['EntityRelation'])

        # Adding model 'Value'
        db.create_table(u'cookies_value', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal(u'cookies', ['Value'])

        # Adding model 'IntegerValue'
        db.create_table(u'cookies_integervalue', (
            (u'value_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Value'], unique=True, primary_key=True)),
            ('value', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'cookies', ['IntegerValue'])

        # Adding model 'TextValue'
        db.create_table(u'cookies_textvalue', (
            (u'value_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Value'], unique=True, primary_key=True)),
            ('value', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'cookies', ['TextValue'])

        # Adding model 'FloatValue'
        db.create_table(u'cookies_floatvalue', (
            (u'value_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Value'], unique=True, primary_key=True)),
            ('value', self.gf('django.db.models.fields.FloatField')()),
        ))
        db.send_create_signal(u'cookies', ['FloatValue'])

        # Adding model 'DateTimeValue'
        db.create_table(u'cookies_datetimevalue', (
            (u'value_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Value'], unique=True, primary_key=True)),
            ('value', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'cookies', ['DateTimeValue'])

        # Adding model 'Event'
        db.create_table(u'cookies_event', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('occurred', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('did', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['cookies.Action'])),
            ('on', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['cookies.Entity'])),
        ))
        db.send_create_signal(u'cookies', ['Event'])

        # Adding model 'Action'
        db.create_table(u'cookies_action', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Action'])

        # Adding model 'Grant'
        db.create_table(u'cookies_grant', (
            (u'action_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Action'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Grant'])

        # Adding model 'Delete'
        db.create_table(u'cookies_delete', (
            (u'action_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Action'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Delete'])

        # Adding model 'Change'
        db.create_table(u'cookies_change', (
            (u'action_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cookies.Action'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cookies', ['Change'])


    def backwards(self, orm):
        # Deleting model 'Authority'
        db.delete_table(u'cookies_authority')

        # Deleting model 'Entity'
        db.delete_table(u'cookies_entity')

        # Deleting model 'Resource'
        db.delete_table(u'cookies_resource')

        # Deleting model 'RemoteResource'
        db.delete_table(u'cookies_remoteresource')

        # Deleting model 'LocalResource'
        db.delete_table(u'cookies_localresource')

        # Deleting model 'Corpus'
        db.delete_table(u'cookies_corpus')

        # Deleting model 'Schema'
        db.delete_table(u'cookies_schema')

        # Removing M2M table for field fields on 'Schema'
        db.delete_table(db.shorten_name(u'cookies_schema_fields'))

        # Deleting model 'Field'
        db.delete_table(u'cookies_field')

        # Deleting model 'FieldRelation'
        db.delete_table(u'cookies_fieldrelation')

        # Deleting model 'ValueRelation'
        db.delete_table(u'cookies_valuerelation')

        # Deleting model 'EntityRelation'
        db.delete_table(u'cookies_entityrelation')

        # Deleting model 'Value'
        db.delete_table(u'cookies_value')

        # Deleting model 'IntegerValue'
        db.delete_table(u'cookies_integervalue')

        # Deleting model 'TextValue'
        db.delete_table(u'cookies_textvalue')

        # Deleting model 'FloatValue'
        db.delete_table(u'cookies_floatvalue')

        # Deleting model 'DateTimeValue'
        db.delete_table(u'cookies_datetimevalue')

        # Deleting model 'Event'
        db.delete_table(u'cookies_event')

        # Deleting model 'Action'
        db.delete_table(u'cookies_action')

        # Deleting model 'Grant'
        db.delete_table(u'cookies_grant')

        # Deleting model 'Delete'
        db.delete_table(u'cookies_delete')

        # Deleting model 'Change'
        db.delete_table(u'cookies_change')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'cookies.action': {
            'Meta': {'object_name': 'Action'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'cookies.authority': {
            'Meta': {'object_name': 'Authority'},
            'endpoint': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'namespace': ('django.db.models.fields.TextField', [], {})
        },
        u'cookies.change': {
            'Meta': {'object_name': 'Change', '_ormbases': [u'cookies.Action']},
            u'action_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Action']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.corpus': {
            'Meta': {'object_name': 'Corpus', '_ormbases': [u'cookies.Resource']},
            u'resource_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Resource']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.datetimevalue': {
            'Meta': {'object_name': 'DateTimeValue', '_ormbases': [u'cookies.Value']},
            'value': ('django.db.models.fields.DateTimeField', [], {}),
            u'value_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Value']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.delete': {
            'Meta': {'object_name': 'Delete', '_ormbases': [u'cookies.Action']},
            u'action_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Action']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.entity': {
            'Meta': {'object_name': 'Entity'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'})
        },
        u'cookies.entityrelation': {
            'Meta': {'object_name': 'EntityRelation', '_ormbases': [u'cookies.FieldRelation']},
            u'fieldrelation_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.FieldRelation']", 'unique': 'True', 'primary_key': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relations_to'", 'to': u"orm['cookies.Entity']"})
        },
        u'cookies.event': {
            'Meta': {'object_name': 'Event'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'did': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cookies.Action']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'occurred': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'on': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cookies.Entity']"})
        },
        u'cookies.field': {
            'Meta': {'object_name': 'Field'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '2'})
        },
        u'cookies.fieldrelation': {
            'Meta': {'object_name': 'FieldRelation'},
            'field': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cookies.Field']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relations_from'", 'to': u"orm['cookies.Entity']"})
        },
        u'cookies.floatvalue': {
            'Meta': {'object_name': 'FloatValue', '_ormbases': [u'cookies.Value']},
            'value': ('django.db.models.fields.FloatField', [], {}),
            u'value_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Value']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.grant': {
            'Meta': {'object_name': 'Grant', '_ormbases': [u'cookies.Action']},
            u'action_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Action']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.integervalue': {
            'Meta': {'object_name': 'IntegerValue', '_ormbases': [u'cookies.Value']},
            'value': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'value_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Value']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.localresource': {
            'Meta': {'object_name': 'LocalResource', '_ormbases': [u'cookies.Resource']},
            'file': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'resource_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Resource']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.remoteresource': {
            'Meta': {'object_name': 'RemoteResource', '_ormbases': [u'cookies.Resource']},
            u'resource_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Resource']", 'unique': 'True', 'primary_key': 'True'}),
            'url': ('django.db.models.fields.TextField', [], {})
        },
        u'cookies.resource': {
            'Meta': {'object_name': 'Resource', '_ormbases': [u'cookies.Entity']},
            'description': ('django.db.models.fields.TextField', [], {}),
            u'entity_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Entity']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.schema': {
            'Meta': {'object_name': 'Schema'},
            'fields': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cookies.Field']", 'symmetrical': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'cookies.textvalue': {
            'Meta': {'object_name': 'TextValue', '_ormbases': [u'cookies.Value']},
            'value': ('django.db.models.fields.TextField', [], {}),
            u'value_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.Value']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cookies.value': {
            'Meta': {'object_name': 'Value'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'cookies.valuerelation': {
            'Meta': {'object_name': 'ValueRelation', '_ormbases': [u'cookies.FieldRelation']},
            u'fieldrelation_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cookies.FieldRelation']", 'unique': 'True', 'primary_key': 'True'}),
            'value': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cookies.Value']"})
        }
    }

    complete_apps = ['cookies']