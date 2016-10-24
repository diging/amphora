import unittest, mock, json, os

from django.test import Client

from cookies.authorization import *
from cookies.models import *

os.environ.setdefault('LOGLEVEL', 'ERROR')

class TestIsOwner(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_is_owner(self):
        resource = Resource.objects.create(
            created_by=self.u,
            name='TestResource'
        )
        self.assertTrue(is_owner(self.u, resource))

    def tearDown(self):
        self.u.delete()


class TestViewAuthEnforcement(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='Test')
        self.end_user = User.objects.create_user(
            username='UnprivelegedUser',
            password='password')
        self.anonymous_user = User.objects.get(username='AnonymousUser')

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

    def test_resource_detail_view_not_public_anonymous(self):
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
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u)
        update_authorizations(['view'], self.end_user, resource)
        path = reverse('resource', args=(resource.id,))
        client = Client()
        client.login(username='UnprivelegedUser', password='password')
        response = client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_resource_detail_view_not_public_deauthorized(self):
        """
        Logged-in users with view auth should able to view non-public
        resources.
        """
        resource = Resource.objects.create(
            name='Test',
            public=True,
            created_by=self.u)
        update_authorizations([], self.anonymous_user, resource)
        path = reverse('resource', args=(resource.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

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

    def test_resource_detail_view_not_public_but_authorized(self):
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

    def test_resource_detail_view_not_public_deauthorized(self):
        """
        Logged-in users with view auth should able to view non-public
        collections.
        """
        collection = Collection.objects.create(
            name='Test',
            public=True,
            created_by=self.u)
        update_authorizations([], self.anonymous_user, collection)
        path = reverse('collection', args=(collection.id,))
        client = Client()
        response = client.get(path)
        self.assertEqual(response.status_code, 403)

    def tearDown(self):
        self.u.delete()
        self.end_user.delete()


class TestAuthLabel(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_auth_label(self):
        resource = Resource.objects.create(created_by=self.u, name='Test')
        collection = Collection.objects.create(created_by=self.u, name='Col')
        entity = ConceptEntity.objects.create(name='what', created_by=self.u)
        relation = Relation.objects.create(
            created_by=self.u,
            name='Rel',
            source=resource,
            predicate=Field.objects.create(name='What'),
            target=entity,
        )

        self.assertEqual(auth_label('view', resource), 'view_resource')
        self.assertEqual(auth_label('change', resource), 'change_resource')
        self.assertEqual(auth_label('add', resource), 'add_resource')
        self.assertEqual(auth_label('delete', resource), 'delete_resource')
        self.assertEqual(auth_label('view_authorizations', resource), 'view_authorizations')
        self.assertEqual(auth_label('change_authorizations', resource), 'change_authorizations')

        self.assertEqual(auth_label('view', collection), 'view_resource')
        self.assertEqual(auth_label('change', collection), 'change_collection')
        self.assertEqual(auth_label('add', collection), 'add_collection')
        self.assertEqual(auth_label('delete', collection), 'delete_collection')
        self.assertEqual(auth_label('view_authorizations', collection), 'view_authorizations')
        self.assertEqual(auth_label('change_authorizations', collection), 'change_authorizations')

        self.assertEqual(auth_label('view', relation), 'view_relation')
        self.assertEqual(auth_label('change', relation), 'change_relation')
        self.assertEqual(auth_label('add', relation), 'add_relation')
        self.assertEqual(auth_label('delete', relation), 'delete_relation')
        self.assertEqual(auth_label('view_authorizations', relation), 'view_authorizations')
        self.assertEqual(auth_label('change_authorizations', relation), 'change_authorizations')

        self.assertEqual(auth_label('view', entity), 'view_entity')
        self.assertEqual(auth_label('change', entity), 'change_conceptentity')
        self.assertEqual(auth_label('add', entity), 'add_conceptentity')
        self.assertEqual(auth_label('delete', entity), 'delete_conceptentity')
        self.assertEqual(auth_label('view_authorizations', entity), 'view_authorizations')
        self.assertEqual(auth_label('change_authorizations', entity), 'change_authorizations')

    def tearDown(self):
        self.u.delete()


class TestUpdateAuthorizations(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')
        self.o = User.objects.create(username='OtherUser')

    def test_update_obj(self):
        """
        :func:`.update_authorizations` should add new authorizations for a user
        on an object.
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        for auth in Resource.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, resource))

        update_authorizations(['view_resource'], self.o, resource)
        self.assertTrue(check_authorization('view_resource', self.o, resource))

    def test_update_obj_shorthand(self):
        """
        :func:`.update_authorizations` should suppoert generic auth names, e.g.
        "view", "change", "delete".
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        auths = ['view', 'change', 'delete', 'change_authorizations',
                 'view_authorizations']
        update_authorizations(auths, self.o, resource)
        self.assertTrue(check_authorization('view_resource', self.o, resource))
        for auth in auths:
            self.assertTrue(check_authorization(auth, self.o, resource))

    def test_update_obj_with_remove(self):
        """
        :func:`.update_authorizations` should remove any authorizations that are
        not included in the ``auths`` argument.
        """

        resource = Resource.objects.create(created_by=self.u, name='Test')
        for auth in Resource.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, resource))

        update_authorizations(['view_resource'], self.o, resource)
        self.assertTrue(check_authorization('view_resource', self.o, resource))

        update_authorizations(['delete_resource'], self.o, resource)
        self.assertFalse(check_authorization('view_resource', self.o, resource))

    def test_update_queryset(self):
        """
        :func:`.update_authorizations` should add new authorizations for a user
        on a a whole queryset.
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        resource2 = Resource.objects.create(created_by=self.u, name='Test2')
        qs = Resource.objects.all()

        for obj in qs:
            for auth in Resource.DEFAULT_AUTHS:
                self.assertFalse(check_authorization(auth, self.o, resource))

        update_authorizations(['view_resource'], self.o, qs)
        for obj in qs:
            self.assertTrue(check_authorization('view_resource', self.o, obj))

    def test_update_queryset_with_remove(self):
        """
        :func:`.update_authorizations` should remove any authorizations that are
        not included in the ``auths`` argument for the whole queryset.
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        resource2 = Resource.objects.create(created_by=self.u, name='Test2')
        qs = Resource.objects.all()

        for obj in qs:
            for auth in Resource.DEFAULT_AUTHS:
                self.assertFalse(check_authorization(auth, self.o, resource))

        update_authorizations(['view_resource'], self.o, qs)
        for obj in qs:
            self.assertTrue(check_authorization('view_resource', self.o, obj))

        update_authorizations(['delete_resource'], self.o, qs)
        for obj in qs:
            self.assertFalse(check_authorization('view_resource', self.o, obj))

    def test_propagate_collection_to_resources(self):
        """
        if ``propagate=True`` (Default), authorizations assigned to a
        :class:`.Collection` should also be applied to its constituent
        :class:`.Resource`\s.
        """
        collection = Collection.objects.create(created_by=self.u, name='Col')
        resource = Resource.objects.create(created_by=self.u, name='Test')
        collection.resources.add(resource)

        for auth in Resource.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, resource))

        update_authorizations(['view_resource'], self.o, collection)
        self.assertTrue(check_authorization('view_resource', self.o, resource),
                        "update_authorizations should propagate to a"
                        " collection's resources.")

        update_authorizations(['delete_collection'], self.o, collection)
        self.assertFalse(check_authorization('view_resource', self.o, resource),
                         "update_authorizations should propagate to a"
                         " collection's resources.")

    def test_propagate_resource_to_relation(self):
        """
        if ``propagate=True`` (Default), authorizations assigned to a
        :class:`.Resource` should also be applied to its constituent
        :class:`.Relation`\s.
        """

        resource = Resource.objects.create(created_by=self.u, name='Test')
        relation = Relation.objects.create(
            created_by=self.u,
            name='Rel',
            source=resource,
            predicate=Field.objects.create(name='What'),
            target=resource,
        )

        for auth in Relation.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, relation))

        update_authorizations(['view_resource'], self.o, resource)
        self.assertTrue(check_authorization('view_relation', self.o, relation),
                        "update_authorizations should propagate to a resource's"
                        " relations.")

        update_authorizations(['delete_resource'], self.o, resource)
        self.assertFalse(check_authorization('view_relation', self.o, relation),
                         "update_authorizations should propagate to a"
                         " resource's relations.")

    def test_propagate_relation_to_conceptentity(self):
        """
        if ``propagate=True`` (Default), authorizations assigned to a
        :class:`.Relation` should also be applied to its constituent
        :class:`.ConceptEntity` instances.
        """

        resource = Resource.objects.create(created_by=self.u, name='Test')
        entity = ConceptEntity.objects.create(name='what', created_by=self.u)
        relation = Relation.objects.create(
            created_by=self.u,
            name='Rel',
            source=resource,
            predicate=Field.objects.create(name='What'),
            target=entity,
        )

        for auth in Relation.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, relation))

        update_authorizations(['view_relation'], self.o, relation)
        self.assertTrue(check_authorization('view_entity', self.o, entity),
                        "update_authorizations should propagate to a relation's"
                        " conceptentities.")


        update_authorizations(['delete_relation'], self.o, relation)
        self.assertFalse(check_authorization('view_entity', self.o, entity),
                         "update_authorizations should propagate to a"
                         " relation's conceptentities.")

    def tearDown(self):
        self.u.delete()
        self.o.delete()


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
        anonymous = User.objects.get(username='AnonymousUser')
        self.assertTrue(check_authorization('view', anonymous, resource))
        self.assertFalse(check_authorization('change', anonymous, resource))

    def test_anonymous_lacks_view_authorization_if_public_is_false(self):
        resource = Resource.objects.create(
            name='Test',
            public=False,
            created_by=self.u)
        anonymous = User.objects.get(username='AnonymousUser')
        self.assertFalse(check_authorization('view', anonymous, resource))
        self.assertFalse(check_authorization('change', anonymous, resource))

    def tearDown(self):
        self.u.delete()


class TestDefaultAuthorizations(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_resource_default_auths(self):
        """
        When a :class:`.Resource` is created, the creator should have all
        of the default authorizations for that object.
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        for auth in Resource.DEFAULT_AUTHS:
            self.assertTrue(check_authorization(auth, self.u, resource))

    def test_collection_default_auths(self):
        """
        When a :class:`.Collection` is created, the creator should have all
        of the default authorizations for that object.
        """
        collection = Collection.objects.create(created_by=self.u, name='Test')
        for auth in Collection.DEFAULT_AUTHS:
            self.assertTrue(check_authorization(auth, self.u, collection))

    def test_conceptentity_default_auths(self):
        """
        When a :class:`.ConceptEntity` is created, the creator should have all
        of the default authorizations for that object.
        """
        entity = ConceptEntity.objects.create(created_by=self.u, name='Test')
        for auth in ConceptEntity.DEFAULT_AUTHS:
            self.assertTrue(check_authorization(auth, self.u, entity))

    def test_relation_default_auths(self):
        """
        When a :class:`.Relation` is created, the creator should have all
        of the default authorizations for that object.
        """
        resource = Resource.objects.create(created_by=self.u, name='Test')
        entity = ConceptEntity.objects.create(created_by=self.u, name='Test')
        relation = Relation.objects.create(
            created_by=self.u,
            source=resource,
            predicate=Field.objects.create(name='test'),
            target=entity
        )
        for auth in Relation.DEFAULT_AUTHS:
            self.assertTrue(check_authorization(auth, self.u, relation))

    def tearDown(self):
        self.u.delete()

# class TestAuthsOnCreation(unittest.TestCase):
#     def setUp(self):
#         self.u = User.objects.create(username='TestUser')
#
