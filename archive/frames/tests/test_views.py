from archive.frames.tests.factories import FrameFactory
from unittest.mock import MagicMock
import boto3
from django.core.urlresolvers import reverse
from django.test import TestCase
import json
import os
import random


class TestFrameGet(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
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
        boto3.client = MagicMock()
        self.header_json = json.load(open(os.path.join(os.path.dirname(__file__), 'frames.json')))
        f = self.header_json[random.choice(list(self.header_json.keys()))]
        f['filename'] = 'testfits.fits'
        f['area'] = [[1, 2], [3, 4]]
        f['version_set'] = [
            {'md5': '8725014a41be8cef2d12cda618fef534', 'key': 'ac44f65c61341e456ffa7898cb5f4449'}
        ]
        self.single_frame_payload = f

    def test_post_frame(self):
        total_frames = len(self.header_json)
        for extension in self.header_json:
            frame_payload = self.header_json[extension]
            frame_payload['filename'] = 'testframe-{0}.fits'.format(extension)
            frame_payload['area'] = [[1, 1], [2, 2]]
            frame_payload['version_set'] = [
                {'md5': 'md5-{0}'.format(extension), 'key': 'key-{0}'.format(extension)}
            ]
            response = self.client.post(
                reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
            )
            self.assertContains(response, frame_payload['filename'], status_code=201)
        response = self.client.get(reverse('frame-list'))
        self.assertEqual(response.json()['count'], total_frames)

    def test_post_missing_data(self):
        frame_payload = self.single_frame_payload
        del frame_payload['filename']
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.json()['filename'], ['This field is required.'])
        self.assertEqual(response.status_code, 400)

    def test_post_duplicate_data(self):
        frame = FrameFactory()
        version = frame.version_set.all()[0]
        frame_payload = self.single_frame_payload
        frame_payload['version_set'] = [{'md5': version.md5, 'key': 'random_key'}]
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.json()['version_set'], [{'md5': ['Version with this md5 already exists.']}])
        self.assertEqual(response.status_code, 400)
