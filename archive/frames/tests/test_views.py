from archive.frames.tests.factories import FrameFactory, VersionFactory
from archive.frames.models import Frame
from archive.authentication.models import Profile
from django.contrib.auth.models import User
from unittest.mock import MagicMock
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.conf import settings
import boto3
import responses
import datetime
import json
import os
import random


class TestFrameGet(TestCase):
    def setUp(self):
        user = User.objects.create(username='admin', password='admin', is_staff=True)
        self.client.force_login(user)
        boto3.client = MagicMock()
        self.frames = FrameFactory.create_batch(5)
        self.frame = self.frames[0]

    def test_get_frame(self):
        response = self.client.get(reverse('frame-detail', args=(self.frame.id, )))
        self.assertEqual(response.json()['basename'], self.frame.basename)

    def test_get_frame_list(self):
        response = self.client.get(reverse('frame-list'))
        self.assertEqual(response.json()['count'], 5)
        self.assertContains(response, self.frame.basename)

    def test_get_frame_list_filter(self):
        response = self.client.get(
            '{0}?basename={1}'.format(reverse('frame-list'), self.frame.basename)
        )
        self.assertEqual(response.json()['count'], 1)
        self.assertContains(response, self.frame.basename)

    def test_filter_area(self):
        frame = FrameFactory.create(
            area='POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))'
        )
        response = self.client.get(
            '{0}?covers=POINT(5 5)'.format(reverse('frame-list'))
        )
        self.assertContains(response, frame.basename)
        response = self.client.get(
            '{0}?covers=POINT(20 20)'.format(reverse('frame-list'))
        )
        self.assertNotContains(response, frame.basename)

    def test_filer_area_wrap_0RA(self):
        frame = FrameFactory.create(
            area='POLYGON((350 -10, 350 10, 10 10, 10 -10, 350 -10))'
        )
        response = self.client.get(
            '{0}?covers=POINT(0 0)'.format(reverse('frame-list'))
        )
        self.assertContains(response, frame.basename)
        response = self.client.get(
            '{0}?covers=POINT(340 0)'.format(reverse('frame-list'))
        )
        self.assertNotContains(response, frame.basename)


class TestFramePost(TestCase):
    def setUp(self):
        user = User.objects.create(username='admin', password='admin', is_staff=True)
        self.client.force_login(user)
        boto3.client = MagicMock()
        self.header_json = json.load(open(os.path.join(os.path.dirname(__file__), 'frames.json')))
        f = self.header_json[random.choice(list(self.header_json.keys()))]
        f['basename'] = FrameFactory.basename.fuzz()
        f['area'] = FrameFactory.area.fuzz()
        f['version_set'] = [
            {
                'md5': VersionFactory.md5.fuzz(),
                'key': VersionFactory.key.fuzz(),
                'extension': VersionFactory.extension.fuzz()
            }
        ]
        self.single_frame_payload = f

    def test_post_frame(self):
        total_frames = len(self.header_json)
        for extension in self.header_json:
            frame_payload = self.header_json[extension]
            frame_payload['basename'] = FrameFactory.basename.fuzz()
            frame_payload['area'] = FrameFactory.area.fuzz()
            frame_payload['version_set'] = [
                {
                    'md5': VersionFactory.md5.fuzz(),
                    'key': VersionFactory.key.fuzz(),
                    'extension': VersionFactory.extension.fuzz()
                }
            ]
            response = self.client.post(
                reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
            )
            self.assertContains(response, frame_payload['basename'], status_code=201)
        response = self.client.get(reverse('frame-list'))
        self.assertEqual(response.json()['count'], total_frames)

    def test_post_missing_data(self):
        frame_payload = self.single_frame_payload
        del frame_payload['basename']
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.json()['basename'], ['This field is required.'])
        self.assertEqual(response.status_code, 400)

    def test_post_duplicate_data(self):
        frame = FrameFactory()
        version = frame.version_set.all()[0]
        frame_payload = self.single_frame_payload
        frame_payload['version_set'] = [
            {'md5': version.md5, 'key': 'random_key', 'extension': '.fits.fz'}
        ]
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.json()['version_set'], [{'md5': ['Version with this md5 already exists.']}])
        self.assertEqual(response.status_code, 400)


class TestFrameFiltering(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        self.admin_user = User.objects.create_superuser(username='admin', email='a@a.com', password='password')
        self.normal_user = User.objects.create(username='frodo', password='theone')
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(PROPID='public', L1PUBDAT=datetime.datetime(2000, 1, 1))
        self.proposal_frame = FrameFactory(PROPID='prop1', L1PUBDAT=datetime.datetime(2099, 1, 1))
        self.not_owned = FrameFactory(PROPID='notyours', L1PUBDAT=datetime.datetime(2099, 1, 1))

    def test_admin_view_all(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('frame-list'))
        self.assertContains(response, self.public_frame.basename)
        self.assertContains(response, self.proposal_frame.basename)
        self.assertContains(response, self.not_owned.basename)

    @responses.activate
    def test_proposal_user(self):
        responses.add(
            responses.GET,
            settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
            body=json.dumps([{'code': 'prop1'}]),
            status=200,
            content_type='application/json'
        )
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('frame-list'))
        self.assertContains(response, self.public_frame.basename)
        self.assertContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    def test_anonymous_user(self):
        response = self.client.get(reverse('frame-list'))
        self.assertContains(response, self.public_frame.basename)
        self.assertNotContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)


class TestZipDownload(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        self.normal_user = User.objects.create(username='frodo', password='theone')
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(PROPID='public', L1PUBDAT=datetime.datetime(2000, 1, 1))
        self.proposal_frame = FrameFactory(PROPID='prop1', L1PUBDAT=datetime.datetime(2099, 1, 1))
        self.not_owned = FrameFactory(PROPID='notyours', L1PUBDAT=datetime.datetime(2099, 1, 1))

    def test_public_download(self):
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [frame.id for frame in Frame.objects.all()]}),
            content_type='application/json'
        )
        self.assertContains(response, self.public_frame.basename)
        self.assertNotContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    @responses.activate
    def test_proposal_download(self):
        responses.add(
            responses.GET,
            settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
            body=json.dumps([{'code': 'prop1'}]),
            status=200,
            content_type='application/json'
        )
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [frame.id for frame in Frame.objects.all()]}),
            content_type='application/json'
        )
        self.assertContains(response, self.public_frame.basename)
        self.assertContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    def test_empty_download(self):
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [self.not_owned.id]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
