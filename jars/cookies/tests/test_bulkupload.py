import django
from django.test import Client
from unittest import TestCase
import zipfile


class MockZipFile:
    ''' Creates a mock zip object'''
    def __init__(self):
        self.files = []
    def __iter__(self):
        return iter(self.files)
    def seek(self):
        pass
    def write(self, fname):
        self.files.append(fname)

class TestBulkUpload(TestCase):


    def create_zip_object(self):
        mck_zip = MockZipFile()
        mck_zip.write("abc.txt")
        mck_zip.write("._abc.txt")
        return mck_zip

    def test_add_bulk_resource(self):
        # Testing mock zip object
        mck_zip = self.create_zip_object()
        z = zipfile.ZipFile(mck_zip)
        for name in z.namelist():
            print name
