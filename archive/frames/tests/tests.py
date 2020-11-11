from archive.frames.tests.factories import FrameFactory
from unittest.mock import patch
from archive.test_helpers import ReplicationTestCase

class TestVersion(ReplicationTestCase):

    @patch('archive.frames.models.Version.delete_data')
    def test_version_delete(self, mock):
        frame = FrameFactory()
        frame.delete()
        self.assertTrue(mock.called)
