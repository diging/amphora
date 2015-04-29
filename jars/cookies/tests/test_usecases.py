import django
from django.test import TestCase, Client
from django.test.client import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.helpers import AdminForm
from django.core.urlresolvers import reverse, resolve

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from cookies.forms import *
from cookies.models import *
from cookies.ingest import ZoteroRDFIngester
from cookies.admin import import_schema

#class CreateLocalResourceCase(TestCase):
#    """
#    3.3.1.1 Use case: Create Local Resource
#    
#    Brief Description
#    -----------------
#    The Curator creates a new Local Resource by uploading a file from their
#    computer.
#    
#    Step-by-Step Description
#    ------------------------
#    The Curator has already accessed the JARS main administrative interface, and
#    may have accessed the Resource change list.
#    
#    1. The Curator selects Add Resource.
#    2. The system presents a choice of adding a local or remote resource.
#    3. The Curator selects to add a local resource.
#    4. The system presents a blank form.
#    5. The Curator enters a resource name, selects a local file, fills optional
#       fields, and submits the form.
#    6. The system validates the form data and creates a new Local Resource
#       object in the database.
#    7. The system returns the Curator to the Resource change list.
#    
#    Postcondition
#    -------------
#    The Local Resource has been added to the database.
#    
#    Other
#    -----
#    Optional fields include Type, and whether the Resource is restricted.
#    """
#
#    def setUp(self):
#        """
#        Create a User, and log them in.
#        """
#        
#        self.rf = RequestFactory()
#
#        self.user = User.objects.create_user('tester', password='secret')
#        self.user.is_superuser = True
#        self.user.is_staff = True
#        self.user.save()
#        
#        self.c = Client()
#        self.c.login(username='tester', password='secret')
#        
#        self.url_prefix = "http://testserver"
#        self.add_url = reverse("admin:cookies_resource_add")
#        self.add_localurl = reverse("admin:cookies_localresource_add")
#        self.list_url = reverse("admin:cookies_resource_changelist")
#        self.locallist_url = reverse("admin:cookies_localresource_changelist")
#
#    def test_add_resource_method(self):
#        """
#        The Curator selects Add Resource. The system presents a choice of adding
#        a local or remote resource.
#        """
#        
#        response = self.c.get(self.add_url, follow=True)
#        
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('form', response.context, 'Response contains no form')
#        self.assertIsInstance(response.context['form'], ChooseResourceTypeForm,
#                'Returns incorrect form'    )
#
#    def test_user_selects_local(self):
#        """
#        The Curator selects to add a local resource. The system presents a blank
#        form.
#        """
#        
#        response = self.c.post(self.add_url, {'resource_type': 'localresource'},
#                    follow=True )
#
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('adminform', response.context,'Response contains no form')
#        self.assertIsInstance(response.context['adminform'], AdminForm,
#                'Returns no AdminForm'  )
#        self.assertEqual(response.context['adminform'].form.Meta.model,
#                LocalResource, 'Returns incorrect Form' )
#
#    def test_user_submits_local_form(self):
#        """
#        The Curator enters a resource name, selects a local file, fills optional
#        fields, and submits the form. The system validates the form data and
#        creates a new Local Resource object in the database. The system returns
#        the Curator to the Resource change list.
#        """
#        
#        with open('./cookies/static/cookies/img/icon_addlink.gif', 'r') as f:
#            data = {
#                'relations_from-TOTAL_FORMS': 1,
#                'relations_from-INITIAL_FORMS': 0,
#                'relations_from-MIN_NUM_FORMS': 0,
#                'relations_from-MAX_NUM_FORMS': 1000,
#                'name': 'TestResource',
#                'file': f,
#                }
#            response = self.c.post(self.add_localurl, data)
#
#        self.assertIsInstance(response, HttpResponseRedirect,
#                'Returns incorrect response'    )
#        
#        self.assertEqual(response.url, self.url_prefix + self.locallist_url,
#                'Redirects to incorrect URL'    )
#
#        # Check database.
#        resource = Resource.objects.filter(name='TestResource')
#        self.assertEqual(resource.count(), 1,
#                'The Resource was not added to the database'  )
#
#class CreateRemoteResourceCase(TestCase):
#    """
#    3.3.1.2 Use case: Create Remote Resource
#    
#    Brief Description
#    -----------------
#    The Curator creates a new Remote Resource by entering the URL of a resource
#    on a remote service.
#    
#    Step-by-Step Description
#    ------------------------
#    The Curator has already accessed the JARS main administrative interface, and
#    may have accessed the Resource change list.
#    
#    1. The Curator selects Add Resource.
#    2. The system presents a choice of adding a local or remote resource.
#    3. The Curator selects to add a remote resource.
#    4. The system presents a blank form.
#    5. The Curator enters a resource name, enters the URL of the remote 
#       resource, fills optional fields (can assign Type, flag as restricted),
#       and submits the form.
#    6. The system validates the form data and creates a new Remote Resource
#       object in the database.
#    7. The system returns the Curator to the Resource change list.
#
#    Postcondition
#    -------------
#    The Remote Resource has been added to the database.
#
#    Other
#    -----
#    Optional fields include Type, and whether the Resource is restricted.
#    """
#
#    def setUp(self):
#        """
#        Create a User, and log them in.
#        """
#        
#        self.rf = RequestFactory()
#
#        self.user = User.objects.create_user('tester', password='secret')
#        self.user.is_superuser = True
#        self.user.is_staff = True
#        self.user.save()
#        
#        self.c = Client()
#        self.c.login(username='tester', password='secret')
#        
#        self.url_prefix = "http://testserver"
#        self.add_url = reverse("admin:cookies_resource_add")
#        self.add_remoteurl = reverse("admin:cookies_remoteresource_add")
#        self.list_url = reverse("admin:cookies_resource_changelist")
#        self.locallist_url = reverse("admin:cookies_localresource_changelist")
#        self.remotelist_url = reverse("admin:cookies_remoteresource_changelist")
#
#    def test_add_resource_method(self):
#        """
#        The Curator selects Add Resource. The system presents a choice of adding
#        a local or remote resource.
#        """
#        
#        response = self.c.get(self.add_url, follow=True)
#        
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('form', response.context, 'Response contains no form')
#        self.assertIsInstance(response.context['form'], ChooseResourceTypeForm,
#                'Returns incorrect form'    )
#
#    def test_user_selects_remote(self):
#        """
#        The Curator selects to add a remote resource. The system presents a 
#        blank form.
#        """
#        
#        response = self.c.post(self.add_url,
#                    {'resource_type': 'remoteresource'}, follow=True )
#
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('adminform', response.context,'Response contains no form')
#        self.assertIsInstance(response.context['adminform'], AdminForm,
#                'Returns no AdminForm'  )
#        self.assertEqual(response.context['adminform'].form.Meta.model,
#                RemoteResource, 'Returns incorrect Form' )
#
#    def test_user_submits_remote_form(self):
#        """
#        The Curator enters a resource name, enters the URL of the remote 
#        resource, fills optional fields (can assign Type, flag as restricted),
#        and submits the form. The system validates the form data and creates a
#        new Remote Resource object in the database. The system returns the
#        Curator to the Resource change list.
#        """
#        
#        data = {
#            'relations_from-TOTAL_FORMS': 1,
#            'relations_from-INITIAL_FORMS': 0,
#            'relations_from-MIN_NUM_FORMS': 0,
#            'relations_from-MAX_NUM_FORMS': 1000,
#            'name': 'TestResource',
#            'url': 'http://some.url/overthere',
#            }
#        response = self.c.post(self.add_remoteurl, data)
#
#        self.assertIsInstance(response, HttpResponseRedirect,
#                'Returns incorrect response'    )
#        self.assertEqual(response.url, self.url_prefix + self.remotelist_url,
#                'Redirects to incorrect URL'    )
#
#        # Check database.
#        resource = Resource.objects.filter(name='TestResource')
#        self.assertEqual(resource.count(), 1,
#                'The Resource was not added to the database'  )
#
#class UpdateMetadataCase(TestCase):
#    """
#    3.3.1.3 Use case: Update Metadata
#    
#    Brief Description
#    -----------------
#    The Curator updates the metadata for a Resource by selecting fields and
#    entering values for those fields.
#    
#    Step-by-Step Description
#    ------------------------
#    The Curator has already accessed the Resource change list.
#    
#    1. The Curator selects a Resource from the Resource change list.
#    2. The system displays a form with existing metadata pre-filled, and an
#       option to add a metadata Field to a resource.
#    3. The Curator selects the desired Field.
#    4. The system adds the field to the Resource metadata, and presents an input
#       for the Field's value.
#    5. The Curator enters a value for the Field, and submits the form.
#    6. The system validates the form data and creates a new metadata Relation
#       object in the database.
#    7. The system returns the Curator to the Resource change list.
#    
#    Alternate Paths
#    ---------------
#    * At step 3, instead of adding a new Field the Curator can change the values
#      of metadata Fields already added to the Resource.
#    * At step 3, the Curator can also delete existing metadata Fields.
#    * At step 5, the Curator can add additional metadata Fields before 
#      submitting the form.
#      
#    Postcondition
#    -------------
#    * A new metadata Relation has been added to the database.
#    * Alternate path A: the values of the modified Relation(s) have been updated
#      in the database.
#    * Alternate path B: the modified Relation(s) have been dropped from the
#      database.
#    * Alternate path C: multiple Relations have been added to the database.
#    """
#
#    def setUp(self):
#        """
#        Create a User, and log them in.
#        """
#        
#        self.rf = RequestFactory()
#
#        self.user = User.objects.create_user('tester', password='secret')
#        self.user.is_superuser = True
#        self.user.is_staff = True
#        self.user.save()
#        
#        self.c = Client()
#        self.c.login(username='tester', password='secret')
#        
#        self.url_prefix = "http://testserver"
#        self.list_url = reverse("admin:cookies_resource_changelist")
#        self.locallist_url = reverse("admin:cookies_localresource_changelist")
#        self.remotelist_url = reverse("admin:cookies_remoteresource_changelist")
#
#        self.resource = LocalResource(name='TestResource')
#        self.resource.save()
#    
#        self.change_url = reverse("admin:cookies_resource_change",
#            args=(self.resource.id,))
#        self.localchange_url = reverse("admin:cookies_localresource_change",
#            args=(self.resource.id,))
#
#
#        self.field = Field(name='TestField')
#        self.field.save()
#
#    def test_choose_resource(self):
#        """
#        The Curator selects a Resource from the Resource change list. The system
#        displays a form with existing metadata pre-filled, and an option to add
#        a metadata Field to a resource.
#        
#        Updated: the system will redirect to the form, hence a 302 response. We
#        don't expect a context or form here, either.
#        """
#
#        # The first response should be a 302 Redirect.
#        response = self.c.get(self.change_url)
#
#        self.assertIsInstance(response, HttpResponse,
#            'Expected HttpResponse, received {0}'.format(type(response))    )
#        self.assertEqual(response.status_code, 302,
#            'Expected status 302 but received {0}'.format(response.status_code))
#
#        # Following the redirect should result in a 200 OK, containing an
#        #  an AdminForm for (in this case) a LocalResource (since our
#        #  test Resource, self.resource, is a LocalResource; it would be
#        #  otherwise for a RemoteResource).
#        response = self.c.get(response.url)
#        
#        self.assertEqual(response.status_code, 200,
#            'Expected status 200 but received {0}'.format(response.status_code))
#        self.assertIn('adminform', response.context,
#            'Response contains no form')
#        
#        form_inst = response.context['adminform']
#        self.assertIsInstance(form_inst, AdminForm,
#            'Returns no AdminForm; got a {0} instead'.format(type(form_inst)))
#        self.assertEqual(form_inst.form.Meta.model, LocalResource,
#            'Expected form for a LocalResource; got a {0} instead'.format(
#                form_inst.form.Meta.model)  )
#
#    def test_submit_change_form(self):
#        """
#        The Curator selects the desired Field. The system adds the field to the
#        Resource metadata, and presents an input for the Field's value. The
#        Curator enters a value for the Field, and submits the form. The system
#        validates the form data and creates a new metadata Relation object in
#        the database. The system returns the Curator to the Resource change
#        list.
#        """
#        data = {
#            'relations_from-TOTAL_FORMS': 1,
#            'relations_from-INITIAL_FORMS': 0,
#            'relations_from-MIN_NUM_FORMS': 0,
#            'relations_from-MAX_NUM_FORMS': 1000,
#            'name': self.resource.name,
#            'relations_from-0-entity_ptr': '',
#            'relations_from-0-source': self.resource.id,
#            'relations_from-0-predicate': self.field.id,
#            'relations_from-0-target': 'Bob',
#            }
#
#        # Since we're changing a LocalResource, we need to post to the
#        #  LocalResource change view.
#        response = self.c.post(self.localchange_url, data)
#        self.assertIsInstance(response, HttpResponseRedirect,
#                'Returns incorrect response'    )
#        
#        self.assertEqual(response.status_code, 302,
#            'Expected status 302 but received {0}'.format(response.status_code))
#        self.assertEqual(response.url, self.url_prefix + self.locallist_url,
#            'Redirects to incorrect URL'    )
#            
#        # If we follow the redirect, we should get another redirect to the
#        #  Resource list view.
#        response = self.c.get(response.url)
#        self.assertEqual(response.status_code, 302,
#            'Expected status 302 but received {0}'.format(response.status_code))
#        self.assertEqual(response.url, self.url_prefix + self.list_url,
#            'Redirects to incorrect URL'    )
#            
#        # If we follow the redirect, we should finally arrive at the Resource
#        #  list view with status 200.
#        response = self.c.get(response.url)
#        self.assertEqual(response.status_code, 200,
#            'Expected status 200 but received {0}'.format(response.status_code))
#
#        # Check database.
#        resource = Resource.objects.get(name='TestResource')
#        self.assertEqual(resource.relations_from.count(), 1,
#                'The Resource was not updated in the database'  )
#        self.assertEqual(resource.relations_from.all()[0].target.name, 'Bob')
#
#class CreateMetadataSchemaManuallyCase(TestCase):
#    """
#    3.3.1.8 Use case: Create Metadata Schema
#    
#    The Curator creates a new Metadata Schema by entering a name for that
#    Schema.
#    
#    Step-by-Step Description
#    ------------------------
#    1. The Curator has already accessed the JARS main administrative interface,
#       and may have accessed the Schema change list.
#    2. The Curator selects to add a Schema.
#    3. The system presents the option to create a schema manually, or from an
#       RDF document.
#    4. The Curator selects to the manual option.
#    5. The system presents a blank form.
#    6. The Curator enters a name for the Schema, and submits the form.
#    7. The system creates a new Schema in the database, and returns the User to
#       the Schema changelist view.
#    
#    Postcondition
#    -------------
#    The Schema has been added to the database.
#    """
#    
#    def setUp(self):
#        """
#        Create a User, and log them in.
#        """
#        
#        self.rf = RequestFactory()
#
#        self.user = User.objects.create_user('tester', password='secret')
#        self.user.is_superuser = True
#        self.user.is_staff = True
#        self.user.save()
#        
#        self.c = Client()
#        self.c.login(username='tester', password='secret')
#        
#        self.url_prefix = "http://testserver"
#        self.add_url = reverse("admin:cookies_schema_add")
#        self.list_url = reverse("admin:cookies_schema_changelist")
#        self.locallist_url = reverse("admin:cookies_localresource_changelist")
#        self.remotelist_url = reverse("admin:cookies_remoteresource_changelist")
#
#    def test_add_schema_method(self):
#        """
#        The Curator selects to add a :class:`.Schema`\. The system presents the
#        option to create a Schema manually, or from an RDF document.
#        """
#
#        response = self.c.get(self.add_url, follow=True)
#        
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('form', response.context, 'Response contains no form')
#        self.assertIsInstance(response.context['form'], ChooseSchemaMethodForm,
#                'Returns incorrect form'    )
#
#    def test_user_selects_manual(self):
#        """
#        The Curator selects to the manual option. The system presents a blank
#        form.
#        """
#
#        response = self.c.post(self.add_url, {'schema_method': 'manual'})
#
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('adminform', response.context,'Response contains no form')
#        self.assertIsInstance(response.context['adminform'], AdminForm,
#                'Returns no AdminForm'  )
#        self.assertEqual(response.context['adminform'].form.Meta.model, Schema,
#                'Returns incorrect Form'    )
#
#    def test_user_submits_manual_form(self):
#        """
#        The Curator enters a name for the Schema, and submits the form. The
#        system creates a new Schema in the database, and returns the User to
#        the Schema changelist view.
#        """
#        
#        data = {
#            'types-TOTAL_FORMS': 1,
#            'types-INITIAL_FORMS': 0,
#            'types-MIN_NUM_FORMS': 0,
#            'types-MAX_NUM_FORMS': 1000,
#            'name': 'TestSchema',
#            'schema_method': 'manual',
#            }
#
#        response = self.c.post(self.add_url, data)
#
#        self.assertIsInstance(response, HttpResponseRedirect,
#                'Returns incorrect response'    )
#        self.assertEqual(response.url, self.url_prefix + self.list_url,
#                'Redirects to incorrect URL'    )
#
#        # Check database.
#        schema = Schema.objects.filter(name='TestSchema')
#        self.assertEqual(schema.count(), 1,
#                'The Schema was not added to the database'  )
#
#class AddMetadataFieldtoSchemaCase(TestCase):
#    """
#    3.3.1.9 Use case: Add Metadata Field to Schema
#    
#    Brief Description
#    -----------------
#    The Curator adds a new metadata field by entering a name for the Field, and
#    optionally selecting domain and range Types, and/or a parent Field. The
#    Curator adds the Field to a Schema by selecting a Schema while adding or
#    editing a Field.
#    
#    Step-by-Step Description
#    ------------------------
#    The Curator has already accessed the JARS main administrative interface, and
#    may have accessed the Field change list.
#    
#    1. The Curator selects to add a Field.
#    2. The system presents a blank form.
#    3. The Curator enters a name for the field, and optionally selects domain
#       and range Types, and/or a parent Field.
#    4. The Curator selects a Schema to which the Field should be added, and
#       submits the form.
#    5. The system creates the new Field in the database, and associates it with
#       the selected Schema.
#       
#    Postcondition
#    -------------
#    The Field has been added to the database, along with a reference to the
#    selected Schema.
#    """
#
#    def setUp(self):
#        """
#        Create a User, and log them in.
#        """
#        
#        self.rf = RequestFactory()
#
#        self.user = User.objects.create_user('tester', password='secret')
#        self.user.is_superuser = True
#        self.user.is_staff = True
#        self.user.save()
#        
#        self.c = Client()
#        self.c.login(username='tester', password='secret')
#        
#        self.url_prefix = "http://testserver"
#        self.add_url = reverse("admin:cookies_field_add")
#        self.list_url = reverse("admin:cookies_field_changelist")
#    
#        self.schema = Schema(   name='TestSchema'   )
#        self.schema.save()
#
#    def test_user_add_field_method(self):
#        """
#        The Curator selects to add a Field. The system presents a blank form.
#        """
#
#        response = self.c.get(self.add_url, follow=True)
#        
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('adminform', response.context,
#                'Response contains no AdminForm'    )
#        self.assertEqual(response.context['adminform'].form.Meta.model,
#                Field, 'Returns incorrect form'    )
#
#    def test_submit_field_form(self):
#        """
#        The Curator enters a name for the field, and optionally selects domain
#        and range Types, and/or a parent Field. The Curator selects a Schema to
#        which the Field should be added, and submits the form. The system 
#        creates the new Field in the database, and associates it with the 
#        selected Schema.
#        """
#
#        data = {
#            'schema': self.schema.id,
#            'name': 'TestField',
#            }
#
#        response = self.c.post(self.add_url, data)
#
#        self.assertIsInstance(response, HttpResponseRedirect,
#                'Returns incorrect response'    )
#        self.assertEqual(response.url, self.url_prefix + self.list_url,
#                'Redirects to incorrect URL'    )
#                
#        # Check the database.
#        field = Field.objects.filter(name='TestField')
#        self.assertEqual(field.count(), 1,
#                'The Field was not added to the database'   )
#        self.assertEqual(field[0].schema.id, self.schema.id,
#                'The Fields was not added to the Schema'    )
#
#
class CreateMetadataSchemaFromRDFCase(TestCase):
    """
    3.3.1.10 Use case: Add Metadata Schema from RDF
    
    Brief Description
    -----------------
    The Curator adds a metadata schema by specifying a remote RDF file.
    
    Step-by-Step Description
    ------------------------
    The Curator has already accessed the JARS main administrative interface, and
    may have accessed the Schema change list.
    
    1. The Curator selects to add a Schema.
    2. The system presents the option to create a schema manually, or from an
       RDF document.
    3. The Curator selects the RDF option.
    4. The system presents a blank form.
    5. The Curator enters a URL for the RDF document and submits the form.
    6. The system reads and interprets the RDF document, and creates a new
       Schema and Fields accordingly.
    
    Postcondition
    -------------
    The Schema and Fields have been added to the database.
    """

    def setUp(self):
        """
        Create a User, and log them in.
        """
        
        self.rf = RequestFactory()

        self.user = User.objects.create_user('tester', password='secret')
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()
        
        self.c = Client()
        self.c.login(username='tester', password='secret')
        
        self.url_prefix = "http://testserver"
        self.add_url = reverse("admin:cookies_schema_add")
        self.list_url = reverse("admin:cookies_schema_changelist")
#
#    def test_user_select_remote(self):
#        """
#        The Curator selects the RDF option. The system presents a blank
#        form.
#        """
#
#        response = self.c.post(self.add_url, {'schema_method': 'remote'})
#
#        self.assertIsInstance(response, HttpResponse,
#                'Returns incorrect response'    )
#        self.assertEqual(response.status_code, 200, 'Response status not OK')
#        self.assertIn('form', response.context,'Response contains no form')
#        self.assertIsInstance(response.context['form'], RemoteSchemaForm,
#                'Returns incorrect Form'  )

    def test_user_submits_remote_form(self):
        """
        The Curator enters a URL for the RDF document and submits the form.
        The system reads and interprets the RDF document, and creates a new 
        Schema and Fields accordingly.
        
        Notes
        -----
        This test currently fails because testserver URLs aren't recognized as
        valid URLs by the form validator.
        """

        data = {
            'schema_name': 'TestRDFSchema',
            'schema_url': self.url_prefix+'/static/cookies/schemas/dcterms.rdf',
            'schema_method': 'remote',
            }

        response = self.c.post(self.add_url, data)
        
        self.assertIsInstance(response, HttpResponse,
            'Returns incorrect response'    )
        self.assertEqual(response.status_code, 200,
            'Expected status 200 but received {0}'.format(response.status_code))

        print data['schema_url']
        # Check the database.
        schema = Schema.objects.filter(name='TestRDFSchema')
        self.assertEqual(schema.count(), 1,
                'The Schema was not added to the database'  )
        self.assertEqual(schema[0].types.count(), 55,
                'The Fields were not added to the database' )

