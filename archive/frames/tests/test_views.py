from archive.frames.tests.factories import FrameFactory
from django.core.urlresolvers import reverse
from django.test import TestCase


class TestFrameGet(TestCase):
    def setUp(self):
        self.frames = FrameFactory.create_batch(5)
        self.frame = self.frames[0]

    def test_get_frame(self):
        response = self.client.get(reverse('frame-detail', args=(self.frame.id, )))
        self.assertEqual(response.json()['filename'], self.frame.filename)

    def test_get_frame_list(self):
        response = self.client.get(reverse('frame-list'))
        self.assertEqual(response.json()['count'], 5)
        self.assertContains(response.json()['results'], self.frame.filename)

    def test_get_frame_list_filter(self):
        response = self.client.get(
            '{}?filename={1}'.format(reverse('frame-list'), self.frame.filename)
        )
        self.assertEqual(response.json()['count'], 1)
        self.asserContains(response.json()['results'], self.frame.filename)
