from django.test import TestCase
from django.db import connections


class ReplicationTestCase(TestCase):
    """
    Redirect queries in tests to the default database.
    This is a workaround for https://code.djangoproject.com/ticket/23718
    """
    databases = {'default', 'replica'}

    @classmethod
    def setUpClass(cls):
        super(ReplicationTestCase, cls).setUpClass()
        connections['replica']._orig_cursor = connections['replica'].cursor
        connections['replica'].cursor = connections['default'].cursor

    @classmethod
    def tearDownClass(cls):
        connections['replica'].cursor = connections['replica']._orig_cursor
        super(ReplicationTestCase, cls).tearDownClass()
