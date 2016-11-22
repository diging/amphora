import unittest, mock, json, os

from django.test import Client
from django.conf import settings

from cookies.authorization import *
from cookies.models import *

os.environ.setdefault('LOGLEVEL', 'ERROR')


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
        entity = ConceptEntity.objects.create(name='Bob')
        relation = Relation.objects.create(source=resource, predicate=Field.objects.create(name='Test'), target=entity)

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
        relation = Relation.objects.create(source=resource, predicate=Field.objects.create(name='Test'), target=value)

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
        on a :class:`.Collection`.
        """

        collection = Collection.objects.create(created_by=self.u, name='Test')
        for auth in Collection.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, collection))

        update_authorizations(['view'], self.o, collection)
        authorized = check_authorization('view', self.o, collection)

        self.assertTrue(authorized)



    def test_update_obj_with_remove(self):
        """
        :func:`.update_authorizations` should remove any authorizations that are
        not included in the ``auths`` argument.
        """

        collection = Collection.objects.create(created_by=self.u, name='Test')
        for auth in Collection.DEFAULT_AUTHS:
            self.assertFalse(check_authorization(auth, self.o, collection))

        update_authorizations(['view'], self.o, collection)
        self.assertTrue(check_authorization('view', self.o, collection))

        update_authorizations(['delete'], self.o, collection)
        self.assertFalse(check_authorization('view', self.o, collection))

    def test_update_queryset(self):
        """
        :func:`.update_authorizations` should add new authorizations for a user
        on a a whole queryset.
        """
        collection = Collection.objects.create(created_by=self.u, name='Test')
        collection2 = Collection.objects.create(created_by=self.u, name='Test2')
        qs = Collection.objects.all()

        for obj in qs:
            for auth in Collection.DEFAULT_AUTHS:
                self.assertFalse(check_authorization(auth, self.o, collection))

        update_authorizations(['view'], self.o, qs)
        for obj in qs:
            self.assertTrue(check_authorization('view', self.o, obj))

    def test_update_queryset_with_remove(self):
        """
        :func:`.update_authorizations` should remove any authorizations that are
        not included in the ``auths`` argument for the whole queryset.
        """
        collection = Collection.objects.create(created_by=self.u, name='Test')
        collection2 = Collection.objects.create(created_by=self.u, name='Test2')
        qs = Collection.objects.all()

        for obj in qs:
            for auth in Collection.DEFAULT_AUTHS:
                self.assertFalse(check_authorization(auth, self.o, collection))

        update_authorizations(['view'], self.o, qs)
        for obj in qs:
            self.assertTrue(check_authorization('view', self.o, obj))

        update_authorizations(['delete'], self.o, qs)
        for obj in qs:
            self.assertFalse(check_authorization('view_resource', self.o, obj))

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


class TestDefaultAuthorizations(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_collection_default_auths(self):
        """
        When a :class:`.Collection` is created, the creator should have all
        of the default authorizations for that object.
        """
        collection = Collection.objects.create(created_by=self.u, name='Test')
        for auth in Collection.DEFAULT_AUTHS:
            self.assertTrue(check_authorization(auth, self.u, collection))

    def tearDown(self):
        self.u.delete()


class TestAuthorizationPropagation(unittest.TestCase):
    def test_propagate_collection_to_resources(self):
        """This is kind of meaningless now."""
        u = User.objects.create(username='Bob')
        collection = Collection.objects.create(name='TheCollection', created_by=u)
        for i in xrange(10):
            collection.resources.add(Resource.objects.create(name='TheTest %i' % i, created_by=u))

        # print '=='*40
        update_authorizations(['view'], u, collection)
        # logger.setLevel('ERROR')

    def tearDown(self):
        for model in [User, Collection, Resource]:
            model.objects.all().delete()


class TestApplyfilter(unittest.TestCase):
    def setUp(self):
        for model in [User, Collection, Resource, Field]:
            model.objects.all().delete()

    def test_filter_collection(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        for i in xrange(5):
            Collection.objects.create(
                name='Test %i' %i,
                created_by=u if i < 3 else u2)

        qs = apply_filter(u, 'view', Collection.objects.all())
        self.assertEqual(qs.count(), 3)

    def test_filter_collection_authorized(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        for i in xrange(5):
            Collection.objects.create(
                name='Test %i' %i,
                created_by=u2)

        qs = apply_filter(u, 'view', Collection.objects.all())
        self.assertEqual(qs.count(), 0)
        update_authorizations(['view'], u, Collection.objects.first())
        qs = apply_filter(u, 'view', Collection.objects.all())
        self.assertEqual(qs.count(), 1)

    def test_filter_resource_authorized(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        collection = Collection.objects.create(name='Test', created_by=u2)
        for i in xrange(5):
            Resource.objects.create(
                name='Test %i' %i,
                created_by=u2,
                belongs_to=collection)

        qs = apply_filter(u, 'view', Resource.objects.all())
        self.assertEqual(qs.count(), 0)
        update_authorizations(['view'], u, collection)
        qs = apply_filter(u, 'view', Resource.objects.all())
        self.assertEqual(qs.count(), 5)

    def test_filter_relation_authorized(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        collection = Collection.objects.create(name='Test', created_by=u2)
        for i in xrange(5):
            r = Resource.objects.create(
                name='Test %i' %i,
                created_by=u2,
                belongs_to=collection)
            Relation.objects.create(
                source=r, target=r,
                predicate=Field.objects.create(name='asdf'))

        qs = apply_filter(u, 'view', Relation.objects.all())
        self.assertEqual(qs.count(), 0)
        update_authorizations(['view'], u, collection)
        qs = apply_filter(u, 'view', Relation.objects.all())
        self.assertEqual(qs.count(), 5)

    def test_filter_conceptentity_authorized(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        collection = Collection.objects.create(name='Test', created_by=u2)
        for i in xrange(5):
            r = Resource.objects.create(
                name='Test %i' %i,
                created_by=u2,
                belongs_to=collection)
            e = ConceptEntity.objects.create(
                name='test',
                created_by=u2,
            )
            Relation.objects.create(
                source=r, target=e,
                predicate=Field.objects.create(name='asdf'))

        qs = apply_filter(u, 'view', ConceptEntity.objects.all())
        self.assertEqual(qs.count(), 0)
        update_authorizations(['view'], u, collection)
        qs = apply_filter(u, 'view', ConceptEntity.objects.all())
        self.assertEqual(qs.count(), 5)

    def test_filter_value_authorized(self):
        u = User.objects.create(username='test')
        u2 = User.objects.create(username='test2')
        collection = Collection.objects.create(name='Test', created_by=u2)
        for i in xrange(5):
            r = Resource.objects.create(
                name='Test %i' %i,
                created_by=u2,
                belongs_to=collection)
            e = Value.objects.create()
            e.name = 'test'
            e.save()

            Relation.objects.create(
                source=r, target=e,
                predicate=Field.objects.create(name='asdf'))

        qs = apply_filter(u, 'view', Value.objects.all())
        self.assertEqual(qs.count(), 0)
        update_authorizations(['view'], u, collection)
        qs = apply_filter(u, 'view', Value.objects.all())
        self.assertEqual(qs.count(), 5)

    def tearDown(self):
        for model in [User, Collection, Resource, Field]:
            model.objects.all().delete()
