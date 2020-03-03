from archive.frames.tests.factories import FrameFactory, VersionFactory, PublicFrameFactory
from archive.frames.models import Frame
from archive.authentication.models import Profile
from django.contrib.auth.models import User
from unittest.mock import MagicMock, patch
from django.utils import timezone
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
        settings.QUEUE_BROKER_URL = 'memory://localhost'
        archive_fits_patcher = patch('kombu.Producer.publish')
        self.addCleanup(archive_fits_patcher.stop)
        self.mock_archive_fits_publish = archive_fits_patcher.start()
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

    def test_post_to_archive_fits_on_successful_frame_creation(self):
        frame_payload = self.single_frame_payload
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.mock_archive_fits_publish.assert_called_once()

    def test_bad_frame_does_not_post_to_archive_fits(self):
        frame_payload = self.single_frame_payload
        frame_payload['DATE-OBS'] = 'iamnotadate'
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.mock_archive_fits_publish.assert_not_called()

    def test_frame_created_but_post_to_archive_fits_fails(self):
        self.mock_archive_fits_publish.side_effect = Exception
        frame_payload = self.single_frame_payload
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)

    def test_bad_area(self):
        frame_payload = self.single_frame_payload
        frame_payload['area']['coordinates'][0] = ['asd', 23]
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_long_exptime(self):
        frame_payload = self.single_frame_payload
        frame_payload['EXPTIME'] = 10.032415
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertContains(response, frame_payload['basename'], status_code=201)

    def test_exptime_way_too_long(self):
        frame_payload = self.single_frame_payload
        frame_payload['EXPTIME'] = 10.03241524124232134
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

    def test_post_version_with_migrated(self):
        frame_payload = self.single_frame_payload
        frame_payload['version_set'][0]['migrated'] = True
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        frame = Frame.objects.get(pk=response.json()['id'])
        self.assertTrue(frame.version_set.first().migrated)

        response = self.client.get(reverse('frame-detail', args=(response.json()['id'],)))
        self.assertTrue(response.json()['version_set'][0]['migrated'])

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

    @responses.activate
    def test_filters_public(self):
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
        proposal_frame = FrameFactory(L1PUBDAT=datetime.datetime(2999, 1, 1, tzinfo=UTC), PROPID='prop1')
        public_frame = PublicFrameFactory()

        for false_string in ['false', 'False', '0']:
            response = self.client.get(reverse('frame-list') + '?public={}'.format(false_string))
            self.assertContains(response, proposal_frame.basename)
            self.assertNotContains(response, public_frame.basename)

        self.client.logout()

        for false_string in ['false', 'False', '0']:
            response = self.client.get(reverse('frame-list') + '?public={}'.format(false_string))
            self.assertNotContains(response, proposal_frame.basename)
            self.assertNotContains(response, public_frame.basename)

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
            data=json.dumps({'frame_ids': [frame.id for frame in Frame.objects.all()], 'uncompress': 'false'}),
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
            data=json.dumps({'frame_ids': [frame.id for frame in Frame.objects.all()], 'uncompress': 'false'}),
            content_type='application/json'
        )
        self.assertContains(response, self.public_frame.basename)
        self.assertContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    def test_empty_download(self):
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [self.not_owned.id], 'uncompress': 'false'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)


class TestFrameAggregate(TestCase):
    def setUp(self):
        boto3.client = MagicMock()
        is_public_date = timezone.now() - datetime.timedelta(days=7)
        is_not_public_date = timezone.now() + datetime.timedelta(days=7)
        FrameFactory.create(OBSTYPE='EXPOSE', TELID='1m0a', SITEID='bpl', INSTRUME='kb46', PROPID='prop1', FILTER='rp',
                            L1PUBDAT=is_public_date)
        FrameFactory.create(OBSTYPE='BIAS', TELID='0m4a', SITEID='coj', INSTRUME='en05', PROPID='prop2', FILTER='V',
                            L1PUBDAT=is_not_public_date)
        FrameFactory.create(OBSTYPE='SKYFLAT', TELID='2m0b', SITEID='ogg', INSTRUME='fl10', PROPID='prop3', FILTER='B',
                            L1PUBDAT=is_public_date)

    def test_frame_aggregate(self):
        response = self.client.get(reverse('frame-aggregate'))
        self.assertEqual(set(response.json()['obstypes']), set(['EXPOSE', 'BIAS', 'SKYFLAT']))
        self.assertEqual(set(response.json()['telescopes']), set(['1m0a', '0m4a', '2m0b']))
        self.assertEqual(set(response.json()['sites']), set(['bpl', 'coj', 'ogg']))
        self.assertEqual(set(response.json()['instruments']), set(['kb46', 'en05', 'fl10']))
        self.assertEqual(set(response.json()['filters']), set(['rp', 'V', 'B']))
        self.assertEqual(set(response.json()['proposals']), set(['prop1', 'prop3']))

    def test_frame_aggregate_filtered(self):
        response = self.client.get(reverse('frame-aggregate') + '?SITEID=ogg')
        self.assertEqual(set(response.json()['obstypes']), set(['SKYFLAT']))
        self.assertEqual(set(response.json()['telescopes']), set(['2m0b']))
        self.assertEqual(set(response.json()['sites']), set(['ogg']))
        self.assertEqual(set(response.json()['instruments']), set(['fl10']))
        self.assertEqual(set(response.json()['filters']), set(['B']))
        self.assertEqual(set(response.json()['proposals']), set(['prop3']))

    def test_frame_aggregate_single_field(self):
        response = self.client.get(reverse('frame-aggregate') + '?aggregate_field=SITEID')
        self.assertEqual(set(response.json()['obstypes']), set([]))
        self.assertEqual(set(response.json()['telescopes']), set([]))
        self.assertEqual(set(response.json()['sites']), set(['bpl', 'coj', 'ogg']))
        self.assertEqual(set(response.json()['instruments']), set([]))
        self.assertEqual(set(response.json()['filters']), set([]))
        self.assertEqual(set(response.json()['proposals']), set([]))

    def test_frame_aggregate_single_field_filtered(self):
        response = self.client.get(reverse('frame-aggregate') + '?INSTRUME=en05&aggregate_field=FILTER')
        self.assertEqual(set(response.json()['obstypes']), set([]))
        self.assertEqual(set(response.json()['telescopes']), set([]))
        self.assertEqual(set(response.json()['sites']), set([]))
        self.assertEqual(set(response.json()['instruments']), set([]))
        self.assertEqual(set(response.json()['filters']), set(['V']))
        self.assertEqual(set(response.json()['proposals']), set([]))

    def test_frame_invalid_aggregate_field(self):
        response = self.client.get(reverse('frame-aggregate') + '?INSTRUME=en05&aggregate_field=iaminvalid')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid aggregate_field', str(response.content))
