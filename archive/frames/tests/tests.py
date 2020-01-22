from archive.frames.tests.factories import FrameFactory
from unittest.mock import patch
from django.test import TestCase


class TestVersion(TestCase):

    @patch('archive.frames.models.Version.delete_data')
    def test_version_delete(self, mock):
        frame = FrameFactory()
        frame.delete()
        self.assertTrue(mock.called)

    @patch('kombu.simple.SimpleQueue.put')
    def test_archived_queue(self, mock):
        frame = FrameFactory.create(version_set__disable_signals=False)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_args[0][0]['frameid'], frame.id)
        self.assertEqual(mock.call_args[0][0]['id'], frame.id)
