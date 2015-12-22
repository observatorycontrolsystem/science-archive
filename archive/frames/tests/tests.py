from django.test import TestCase
from archive.frames.tests.factories import FrameFactory


class TestFrame(TestCase):
    def test_frame_url(self):
        frame = FrameFactory()
        self.assertEqual(frame.url, frame.version_set.all()[0].url)
