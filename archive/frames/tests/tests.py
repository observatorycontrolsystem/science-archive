from archive.frames.tests.factories import FrameFactory
from unittest.mock import patch
from django.test import TestCase


class TestVersion(TestCase):

    @patch('archive.frames.models.Version.delete_data')
    def test_version_delete(self, mock):
        frame = FrameFactory()
        frame.delete()
        self.assertTrue(mock.called)
