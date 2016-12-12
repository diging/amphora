import unittest, mock, json, os

from django.test import Client
from django.conf import settings

os.environ.setdefault('LOGLEVEL', 'ERROR')

from cookies.authorization import *
from cookies.models import *




class TestIsOwner(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_is_owner(self):
        resource = Collection.objects.create(
            created_by=self.u,
            name='TestResource'
        )
        self.assertTrue(is_owner(self.u, resource))

    def tearDown(self):
        self.u.delete()


class TestAuthsDependOnCollection(unittest.TestCase):
    def setUp(self):
        for model in [User, Resource, Collection, Field]:
            model.objects.all().delete()

    def test_resource_auth_depends_on_collection(self):
        u = User.objects.create(username='TestUser')
        collection = Collection.objects.create(name='TestCollection')
        resource = Resource.objects.create(name='TestResource',
                                           belongs_to=collection)
        update_authorizations(['view'], u, collection)
        self.assertTrue(check_authorization('view', u, resource),
                        "Authorizations for Resources should depend only on"
                        " the Collection to which they belong.")

        update_authorizations([], u, collection)
        self.assertFalse(check_authorization('view', u, resource),
                        "Authorizations for Resources should depend only on"
                        " the Collection to which they belong.")

        update_authorizations(['view'], u, resource)
        self.assertFalse(check_authorization('view', u, resource),
                        "Authorizations for Resources should depend only on"
                        " the Collection to which they belong.")

    def test_conceptentity_auth_depends_on_collection(self):
        u = User.objects.create(username='TestUser')
        collection = Collection.objects.create(name='TestCollection')
        resource = Resource.objects.create(name='TestResource',
                                           belongs_to=collection)
        entity = ConceptEntity.objects.create(name='Bob')
        Relation.objects.create(source=resource, predicate=Field.objects.create(name='Test'), target=entity)

        update_authorizations(['view'], u, collection)
        self.assertTrue(check_authorization('view', u, entity),
                          "Authorizations for ConceptEntity instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, collection)
        self.assertFalse(check_authorization('view', u, entity),
                          "Authorizations for ConceptEntity instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, entity)
        self.assertFalse(check_authorization('view', u, entity),
                          "Authorizations for ConceptEntity instances should"
                          " depend only on the Resource to which they belong.")

    def test_relation_auth_depends_on_collection(self):
        u = User.objects.create(username='TestUser')
        collection = Collection.objects.create(name='TestCollection')
        resource = Resource.objects.create(name='TestResource',
                                           belongs_to=collection)
        entity = ConceptEntity.objects.create(name='Bob', belongs_to=collection)
        relation = Relation.objects.create(source=resource, predicate=Field.objects.create(name='Test'), target=entity, belongs_to=collection)

        update_authorizations(['view'], u, collection)
        self.assertTrue(check_authorization('view', u, relation),
                          "Authorizations for Relation instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, collection)
        self.assertFalse(check_authorization('view', u, relation),
                          "Authorizations for Relation instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, relation)
        self.assertFalse(check_authorization('view', u, relation),
                          "Authorizations for Relation instances should"
                          " depend only on the Resource to which they belong.")

    def test_value_auth_depends_on_collection(self):
        u = User.objects.create(username='TestUser')
        collection = Collection.objects.create(name='TestCollection')
        resource = Resource.objects.create(name='TestResource',
                                           belongs_to=collection)
        value = Value.objects.create()
        value.name = 'Bob'
        value.save()
        relation = Relation.objects.create(source=resource, predicate=Field.objects.create(name='Test'), target=value, belongs_to=collection)

        update_authorizations(['view'], u, collection)
        self.assertTrue(check_authorization('view', u, value),
                          "Authorizations for Value instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, collection)
        self.assertFalse(check_authorization('view', u, value),
                          "Authorizations for Value instances should"
                          " depend only on the Resource to which they belong.")

        update_authorizations([], u, value)
        self.assertFalse(check_authorization('view', u, value),
                          "Authorizations for Value instances should"
                          " depend only on the Resource to which they belong.")

    def tearDown(self):
        for model in [User, Resource, Collection, Field]:
            model.objects.all().delete()

class TestViewAuthEnforcement(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='Test')
        self.end_user = User.objects.create_user(
            username='UnprivelegedUser',
            password='password')
        self.anonymous_user, _ = User.objects.get_or_create(username='AnonymousUser')

    def test_resource_detail_view_not_public_anonymous(self):
        """
        Anonymous users should not be able to view non-public resources.
        """
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u)

        path = reverse('resource', args=(resource.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

    def test_resource_detail_view_not_public_loggedin(self):
        """
        Logged-in users without view auth should not be able to view non-public
        resources.
        """
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u)

        path = reverse('resource', args=(resource.id,))
        client = Client()
        client.login(username='UnprivelegedUser')
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

    def test_resource_detail_view_not_public_but_authorized(self):
        """
        Logged-in users with view auth should able to view non-public
        resources.
        """
        collection = Collection.objects.create(name='test')
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u,
            belongs_to=collection)
        update_authorizations(['view'], self.end_user, collection)
        path = reverse('resource', args=(resource.id,))
        client = Client()
        client.login(username='UnprivelegedUser', password='password')
        response = client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_resource_detail_view_not_public_deauthorized(self):
        """
        Public means public.
        """
        collection = Collection.objects.create(name='test')
        resource = Resource.objects.create(
            name='Test',
            public=True,
            created_by=self.u,
            belongs_to=collection)
        update_authorizations([], self.anonymous_user, collection)
        path = reverse('resource', args=(resource.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_collection_detail_view_not_public_anonymous(self):
        """
        Anonymous users should not be able to view non-public resources.
        """
        collection = Collection.objects.create(
            name='Test',
            public=False,
            created_by=self.u)

        path = reverse('collection', args=(collection.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

    def test_collection_detail_view_not_public_anonymous(self):
        """
        Logged-in users without view auth should not be able to view non-public
        collections.
        """
        collection = Collection.objects.create(
            name='Test',
            public=False,
            created_by=self.u)

        path = reverse('collection', args=(collection.id,))
        client = Client()
        client.login(username='UnprivelegedUser')
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

    def test_collection_detail_view_not_public_but_authorized(self):
        """
        Logged-in users with view auth should able to view non-public
        collections.
        """
        collection = Collection.objects.create(
            name='Test',
            public=False,
            created_by=self.u)
        update_authorizations(['view'], self.end_user, collection)
        path = reverse('collection', args=(collection.id,))
        client = Client()
        client.login(username='UnprivelegedUser', password='password')
        response = client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_collection_detail_view_not_public_deauthorized(self):
        """
        Public means public.
        """
        collection = Collection.objects.create(
            name='Test',
            public=True,
            created_by=self.u)
        update_authorizations([], self.anonymous_user, collection)
        path = reverse('collection', args=(collection.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.u.delete()
        self.end_user.delete()




class TestPublicBehaviour(unittest.TestCase):
    """
    Earlier versions relied on Resource.public to control view authorizations.
    """
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_anonymous_has_view_authorization_if_public(self):
        resource = Resource.objects.create(
            name='Test',
            public=True,
            created_by=self.u)
        anonymous, _ = User.objects.get_or_create(username='AnonymousUser')
        self.assertTrue(check_authorization('view', anonymous, resource))
        self.assertFalse(check_authorization('change', anonymous, resource))

    def test_anonymous_lacks_view_authorization_if_public_is_false(self):
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u)
        anonymous, _ = User.objects.get_or_create(username='AnonymousUser')
        self.assertFalse(check_authorization('view', anonymous, resource))
        self.assertFalse(check_authorization('change', anonymous, resource))

    def tearDown(self):
        self.u.delete()
