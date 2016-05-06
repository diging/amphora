from django.core.files.uploadhandler import FileUploadHandler
from django.core.files.uploadedfile import UploadedFile

import tempfile
import os
from django.conf import settings


class PersistentTemporaryUploadedFile(UploadedFile):
    """
    A file uploaded to a temporary location (i.e. stream-to-disk). This is
    identical to :class:`django.core.files.uploadedfile.TemporaryUploadedFile`
    except that the :class:`tempfile.NamedTemporaryFile` that it creates will
    not auto-destruct.
    """
    def __init__(self, name, content_type, size, charset,
                 content_type_extra=None):
        if settings.FILE_UPLOAD_TEMP_DIR:
            file = tempfile.NamedTemporaryFile(
                suffix='.upload',
                dir=settings.FILE_UPLOAD_TEMP_DIR,
                delete=False)
        else:
            file = tempfile.NamedTemporaryFile(suffix='.upload', delete=False)

        # The worker who accesses this file after upload may not be running as
        #  the same user as the main application.
        os.chmod(file.name, 0664)
        super(PersistentTemporaryUploadedFile, self).__init__(
            file, name,
            content_type,
            size, charset,
            content_type_extra)

    def temporary_file_path(self):
        """
        Returns the full path of this file.
        """
        return self.file.name

    def close(self):
        try:
            return self.file.close()
        except OSError as e:
            if e.errno != errno.ENOENT:
                # Means the file was moved or deleted before the tempfile
                # could unlink it.  Still sets self.file.close_called and
                # calls self.file.file.close() before the exception
                raise


class PersistentTemporaryFileUploadHandler(FileUploadHandler):
    """
    Upload handler that streams data into a temporary file. This is identical
    to :class:`django.core.files.uploadhandler.TemporaryFileUploadHandler`
    except that it uses :class:`.PersistentTemporaryUploadedFile`.
    """
    def __init__(self, *args, **kwargs):
        super(PersistentTemporaryFileUploadHandler, self).__init__(*args,
                                                                   **kwargs)

    def new_file(self, *args, **kwargs):
        """
        Create the file object to append to as data is coming in.
        """
        super(PersistentTemporaryFileUploadHandler, self).new_file(*args,
                                                                   **kwargs)
        self.file = PersistentTemporaryUploadedFile(self.file_name,
                                                    self.content_type,
                                                    0,
                                                    self.charset,
                                                    self.content_type_extra)

    def receive_data_chunk(self, raw_data, start):
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        self.file.size = file_size
        return self.file
