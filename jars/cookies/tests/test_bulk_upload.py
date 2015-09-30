import unittest
from cookies.forms import validatefiletype
from django.core.files import File
from django.core.exceptions import ValidationError


class TestBulkUpload(unittest.TestCase):
    """
    This class tests the validator (to test proper file type - ZIP file) used in
    bulk upload form.
    """
    def test_zip_file(self):
        """
        When file is a zip file, no exception should be raised.
        """
        f = File('zipfile')
        f.content_type = 'application/zip'
        try:
            validatefiletype(f)
        except ValidationError:
            self.fail('Should not raise Validation Error on a ZIP file.')


    def test_not_a_zip_file(self):
        """
        When file is not a zip file, ValidationError should be raised.
        """
        f = File('notazipfile')
        f.content_type = 'rdf'
        with self.assertRaises(ValidationError):
            validatefiletype(f)
