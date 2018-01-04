from archive.frames.tests.factories import FrameFactory, VersionFactory, PublicFrameFactory
from archive.frames.models import Frame
from archive.authentication.models import Profile
from django.contrib.auth.models import User
from unittest.mock import MagicMock
from django.urls import reverse
from django.test import TestCase
from django.conf import settings
from django.contrib.gis.geos import Point
from pytz import UTC
import boto3
import responses
import datetime
import json
import os
import random


class TestFrameGet(TestCase):
    def setUp(self):
        user = User.objects.create(username='admin', password='admin', is_superuser=True)
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
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

    def test_get_related(self):
        frame = FrameFactory.create()
        related_frame = FrameFactory.create(related_frames=[frame])
        response = self.client.get(reverse('frame-related', args=(frame.id,)))
        self.assertContains(response, related_frame.basename)

    def test_get_headers(self):
        frame = FrameFactory.create()
        response = self.client.get(reverse('frame-headers', args=(frame.id,)))
        self.assertContains(response, frame.headers.data['TRACKNUM'])


class TestFramePost(TestCase):
    def setUp(self):
        user = User.objects.create(username='admin', password='admin', is_superuser=True)
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        self.client.force_login(user)
        boto3.client = MagicMock()
        self.header_json = json.load(open(os.path.join(os.path.dirname(__file__), 'frames.json')))
        f = self.header_json[random.choice(list(self.header_json.keys()))]
        f['basename'] = FrameFactory.basename.fuzz()
        f['area'] = FrameFactory.area.fuzz(as_dict=True)
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
            frame_payload['area'] = FrameFactory.area.fuzz(as_dict=True)
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

    def test_bad_area(self):
        frame_payload = self.single_frame_payload
        frame_payload['area']['coordinates'][0] = ['asd', 23]
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_post_frame_polygon_serialization(self):
        frame_payload = self.single_frame_payload
        frame_payload['area']['coordinates'] = [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Frame.objects.filter(area__covers=Point(5, 5)))
        self.assertFalse(Frame.objects.filter(area__covers=Point(50, 50)))

    def test_post_frame_deserialization(self):
        frame_payload = self.single_frame_payload
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        for idx, coords in enumerate(frame_payload['area']['coordinates']):
            for idy, sub_coord in enumerate(coords):
                for idz, real_coord in enumerate(sub_coord):
                    self.assertAlmostEqual(real_coord, response.json()['area']['coordinates'][idx][idy][idz])

    def test_post_missing_data(self):
        frame_payload = self.single_frame_payload
        del frame_payload['basename']
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.json()['basename'], ['This field is required.'])
        self.assertEqual(response.status_code, 400)

    def test_post_non_required_data(self):
        frame_payload = self.single_frame_payload
        del frame_payload['REQNUM']
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get(reverse('frame-detail', args=(response.json()['id'],)))
        self.assertIsNone(response.json()['REQNUM'])

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
        self.assertEqual(response.json()['version_set'], [{'md5': ['version with this md5 already exists.']}])
        self.assertEqual(response.status_code, 400)


class TestFrameFiltering(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        self.admin_user = User.objects.create_superuser(username='admin', email='a@a.com', password='password')
        self.admin_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        self.normal_user = User.objects.create(username='frodo', password='theone')
        self.normal_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(PROPID='public', L1PUBDAT=datetime.datetime(2000, 1, 1, tzinfo=UTC))
        self.proposal_frame = FrameFactory(PROPID='prop1', L1PUBDAT=datetime.datetime(2099, 1, 1, tzinfo=UTC))
        self.not_owned = FrameFactory(PROPID='notyours', L1PUBDAT=datetime.datetime(2099, 1, 1, tzinfo=UTC))

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
            settings.ODIN_OAUTH_CLIENT['PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'prop1'}]}),
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


class TestQueryFiltering(TestCase):
    def setUp(self):
        boto3.client = MagicMock()

    def test_start_end(self):
        frame = PublicFrameFactory(DATE_OBS=datetime.datetime(2011, 2, 1, tzinfo=UTC))
        response = self.client.get(reverse('frame-list') + '?start=2011-01-01&end=2011-03-01')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?start=2012-01-01&end=2012-03-01')
        self.assertNotContains(response, frame.basename)

    def test_basename(self):
        frame = PublicFrameFactory(basename='allyourbase')
        response = self.client.get(reverse('frame-list') + '?basename=allyour')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?basename=allyourbase')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?basename=cats')
        self.assertNotContains(response, frame.basename)

    def test_object(self):
        frame = PublicFrameFactory(OBJECT='planet9')
        response = self.client.get(reverse('frame-list') + '?OBJECT=planet')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?OBJECT=planet9')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?OBJECT=mars')
        self.assertNotContains(response, frame.basename)

    def test_exptime(self):
        frame = PublicFrameFactory(EXPTIME=300)
        response = self.client.get(reverse('frame-list') + '?EXPTIME=300')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?EXPTIME=200')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?EXPTIME=900')
        self.assertNotContains(response, frame.basename)

    def test_public(self):
        frame = PublicFrameFactory()
        response = self.client.get(reverse('frame-list'))
        self.assertContains(response, frame.basename)
        frame = FrameFactory(L1PUBDAT=datetime.datetime(2999, 1, 1, tzinfo=UTC))
        response = self.client.get(reverse('frame-list'))
        self.assertNotContains(response, frame.basename)

    @responses.activate
    def test_not_public(self):
        user = User.objects.create(username='frodo', password='theone')
        Profile.objects.create(user=user)
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        responses.add(
            responses.GET,
            settings.ODIN_OAUTH_CLIENT['PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'prop1'}]}),
            status=200,
            content_type='application/json'
        )
        self.client.force_login(user)
        frame = FrameFactory(L1PUBDAT=datetime.datetime(2999, 1, 1, tzinfo=UTC), PROPID='prop1')
        response = self.client.get(reverse('frame-list') + '?public=false')
        self.assertContains(response, frame.basename)

        self.client.logout()
        response = self.client.get(reverse('frame-list') + '?public=false')
        self.assertNotContains(response, frame.basename)

    def test_area_covers(self):
        frame = PublicFrameFactory.create(
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

    def test_area_covers_wrap_0ra(self):
        frame = PublicFrameFactory.create(
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

    def test_area_intersects(self):
        frame = PublicFrameFactory.create(
            area='POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))'
        )
        response = self.client.get(
            reverse('frame-list') + '?intersects=POLYGON((-10 -10, -10 20, 20 20, 20 0, -10 -10))'
        )
        self.assertContains(response, frame.basename)

    def test_rlevel(self):
        frame = PublicFrameFactory(RLEVEL=10)
        response = self.client.get(reverse('frame-list') + '?RLEVEL=10')
        self.assertContains(response, frame.basename)

        response = self.client.get(reverse('frame-list') + '?RLEVEL=11')
        self.assertNotContains(response, frame.basename)


class TestZipDownload(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        self.normal_user = User.objects.create(username='frodo', password='theone')
        self.normal_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(PROPID='public', L1PUBDAT=datetime.datetime(2000, 1, 1, tzinfo=UTC))
        self.proposal_frame = FrameFactory(PROPID='prop1', L1PUBDAT=datetime.datetime(2099, 1, 1, tzinfo=UTC))
        self.not_owned = FrameFactory(PROPID='notyours', L1PUBDAT=datetime.datetime(2099, 1, 1, tzinfo=UTC))

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
            settings.ODIN_OAUTH_CLIENT['PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'prop1'}]}),
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


class TestFrameAggregate(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        FrameFactory.create(OBSTYPE='EXPOSE', TELID='1m0a', SITEID='bpl', INSTRUME='kb46')
        FrameFactory.create(OBSTYPE='BIAS', TELID='0m4a', SITEID='coj', INSTRUME='en05')
        FrameFactory.create(OBSTYPE='SKYFLAT', TELID='2m0b', SITEID='ogg', INSTRUME='fl10')

    def test_frame_aggregate(self):
        response = self.client.get(reverse('frame-aggregate'))
        self.assertEqual(set(response.json()['obstypes']), set(['EXPOSE', 'BIAS', 'SKYFLAT']))
        self.assertEqual(set(response.json()['telescopes']), set(['1m0a', '0m4a', '2m0b']))
        self.assertEqual(set(response.json()['sites']), set(['bpl', 'coj', 'ogg']))
        self.assertEqual(set(response.json()['instruments']), set(['kb46', 'en05', 'fl10']))
