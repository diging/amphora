import unittest, mock, json

from cookies import authorization
from cookies.models import *


class TestIsOwner(unittest.TestCase):
    def setUp(self):
        self.u = User.objects.create(username='TestUser')

    def test_is_owner(self):
        resource = Resource.objects.create(
            created_by=self.u,
            name='TestResource'
        )
        self.assertTrue(authorization.is_owner(u, resource))

    def tearDown(self):
        self.u.delete()
