from archive.frames.tests.factories import FrameFactory
from django.core.urlresolvers import reverse
from django.test import TestCase
import json
import os


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
        self.assertContains(response, self.frame.filename)

    def test_get_frame_list_filter(self):
        response = self.client.get(
            '{0}?filename={1}'.format(reverse('frame-list'), self.frame.filename)
        )
        self.assertEqual(response.json()['count'], 1)
        self.assertContains(response, self.frame.filename)


class TestFramePost(TestCase):
    def setUp(self):
        self.header_json = json.load(open(os.path.join(os.path.dirname(__file__), 'frames.json')))

    def test_post_frame(self):
        for extension in self.header_json:
            frame_payload = self.header_json[extension]
            frame_payload['filename'] = 'testframe-{0}.fits'.format(extension)
            frame_payload['area'] = [[1, 1], [2, 2]]
            frame_payload['version_set'] = [
                {'md5': 'md5-{0}'.format(extension), 'key': 'key-{0}'.format(extension)}
            ]
            response = self.client.post(
                reverse('frame-list'), json.dumps(frame_payload), content_type="application/json"
            )
            self.assertEqual(response.status_code, 201)
