from archive.frames.tests.factories import FrameFactory, VersionFactory, PublicFrameFactory
from archive.frames.models import Frame
from archive.authentication.models import Profile
from django.contrib.auth.models import User
from unittest.mock import MagicMock, patch
from django.utils import timezone
from django.urls import reverse
from archive.test_helpers import ReplicationTestCase
from django.conf import settings
from django.contrib.gis.geos import Point
from pytz import UTC
from rest_framework import status
import boto3
import responses
import datetime
import json
import os
import random
import subprocess

from ocs_archive.input.file import EmptyFile
from ocs_archive.input.fitsfile import FitsFile


class TestFrameGet(ReplicationTestCase):
    def setUp(self):
        user = User.objects.create(username='admin', password='admin', is_superuser=True)
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        self.client.force_login(user)
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


class TestFramePost(ReplicationTestCase):
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
        headers = self.header_json[random.choice(list(self.header_json.keys()))]
        datafile = FitsFile(EmptyFile('test.fits'), file_metadata=headers)
        f = datafile.get_header_data().get_archive_frame_data()
        f['headers'] = headers
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
            headers = self.header_json[extension]
            datafile = FitsFile(EmptyFile('test.fits'), file_metadata=headers)
            frame_payload = datafile.get_header_data().get_archive_frame_data()
            frame_payload['headers'] = headers
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
        frame_payload['observation_date'] = 'iamnotadate'
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
        frame_payload['exposure_time'] = 10.032415
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertContains(response, frame_payload['basename'], status_code=201)

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
        del frame_payload['request_id']
        response = self.client.post(
            reverse('frame-list'), json.dumps(frame_payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get(reverse('frame-detail', args=(response.json()['id'],)))
        self.assertIsNone(response.json()['request_id'])

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


class TestFrameFiltering(ReplicationTestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin', email='a@a.com', password='password')
        self.admin_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        self.normal_user = User.objects.create(username='frodo', password='theone')
        self.normal_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(proposal_id='public', public_date=datetime.datetime(2000, 1, 1, tzinfo=UTC))
        self.proposal_frame = FrameFactory(proposal_id='prop1', public_date=datetime.datetime(2099, 1, 1, tzinfo=UTC))
        self.not_owned = FrameFactory(proposal_id='notyours', public_date=datetime.datetime(2099, 1, 1, tzinfo=UTC))

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
            settings.OAUTH_CLIENT['PROFILE_URL'],
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


class TestQueryFiltering(ReplicationTestCase):
    def test_start_end(self):
        frame = PublicFrameFactory(observation_date=datetime.datetime(2011, 2, 1, tzinfo=UTC))
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
        frame = PublicFrameFactory(target_name='planet9')
        response = self.client.get(reverse('frame-list') + '?OBJECT=planet')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?OBJECT=planet9')
        self.assertContains(response, frame.basename)
        response = self.client.get(reverse('frame-list') + '?OBJECT=mars')
        self.assertNotContains(response, frame.basename)

    def test_exptime(self):
        frame = PublicFrameFactory(exposure_time=300)
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
            settings.OAUTH_CLIENT['PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'prop1'}]}),
            status=200,
            content_type='application/json'
        )
        self.client.force_login(user)
        proposal_frame = FrameFactory(public_date=datetime.datetime(2999, 1, 1, tzinfo=UTC), proposal_id='prop1')
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
        frame = PublicFrameFactory(reduction_level=10)
        response = self.client.get(reverse('frame-list') + '?RLEVEL=10')
        self.assertContains(response, frame.basename)

        response = self.client.get(reverse('frame-list') + '?RLEVEL=11')
        self.assertNotContains(response, frame.basename)


class TestZipDownload(ReplicationTestCase):
    def setUp(self):
        self.normal_user = User.objects.create(username='frodo', password='theone')
        self.normal_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        Profile(user=self.normal_user, access_token='test', refresh_token='test').save()
        self.public_frame = FrameFactory(proposal_id='public', public_date=datetime.datetime(2000, 1, 1, tzinfo=UTC))
        self.proposal_frame = FrameFactory(proposal_id='prop1', public_date=datetime.datetime(2099, 1, 1, tzinfo=UTC))
        self.not_owned = FrameFactory(proposal_id='notyours', public_date=datetime.datetime(2099, 1, 1, tzinfo=UTC))

    def test_public_download(self):
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [frame.id for frame in Frame.objects.all()], 'uncompress': 'false'}),
            content_type='application/json'
        )
        self.assertContains(response, self.public_frame.basename)
        self.assertNotContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    @patch('archive.frames.utils.subprocess')
    def test_public_download_uncompressed(self, mock_subprocess):
        mock_proc = MagicMock()
        mock_proc.stdout = b'test_value'
        mock_subprocess.run.return_value = mock_proc
        version = self.public_frame.version_set.first()
        version.extension = '.fits.fz'
        version.save()

        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [self.public_frame.id], 'uncompress': 'true'}),
            content_type='application/json'
        )

        self.assertContains(response, self.public_frame.basename)
        self.assertNotContains(response, self.proposal_frame.basename)
        self.assertNotContains(response, self.not_owned.basename)

    def test_public_download_uncompressed_failure(self):
        response = self.client.post(
            reverse('frame-zip'),
            data=json.dumps({'frame_ids': [num for num in range(1, 20)], 'uncompress': 'true'}),
            content_type='application/json'
        )

        self.assertContains(response,
                            'A maximum of 10 frames can be downloaded with the uncompress flag. Please '
                            'try again with fewer frame_ids.',
                            status_code=status.HTTP_400_BAD_REQUEST)

    @responses.activate
    def test_proposal_download(self):
        responses.add(
            responses.GET,
            settings.OAUTH_CLIENT['PROFILE_URL'],
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


class TestFunpackViewSet(ReplicationTestCase):
    def setUp(self):
        self.frame = FrameFactory(observation_day=datetime.datetime(2020, 11, 18, tzinfo=UTC))

    @patch('archive.frames.views.subprocess')
    def test_funpack_download(self, mock_subprocess):
        """Test that funpack download endpoint returns correct file content and calls funpack."""
        mock_proc = MagicMock()
        mock_proc.stdout = b'test_value'
        mock_subprocess.run.return_value = mock_proc
        response = self.client.get(reverse('frame-funpack-funpack', kwargs={'pk': self.frame.version_set.first().id}))
        mock_subprocess.run.assert_called_with(
            ['/usr/bin/funpack', '-C', '-S', '-'], input=b'', stdout=mock_subprocess.PIPE
        )
        self.assertContains(response, b'test_value')

    @patch.object(subprocess, 'run')
    def test_funpack_download_failure(self, mock_run):
        """Test that funpack download endpoint returns correct response following a failure."""
        mock_run.side_effect = subprocess.CalledProcessError(-9, 'funpack')

        response = self.client.get(reverse('frame-funpack-funpack', kwargs={'pk': self.frame.version_set.first().id}))

        self.assertContains(response,
                            'There was a problem downloading your files. Please try again later or select fewer files.',
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestFrameAggregate(ReplicationTestCase):
    def setUp(self):
        is_public_date = timezone.now() - datetime.timedelta(days=7)
        is_not_public_date = timezone.now() + datetime.timedelta(days=7)
        FrameFactory.create(configuration_type='EXPOSE', telescope_id='1m0a', site_id='bpl', instrument_id='kb46',
                            proposal_id='prop1', primary_optical_element='rp', public_date=is_public_date)
        FrameFactory.create(configuration_type='BIAS', telescope_id='0m4a', site_id='coj', instrument_id='en05',
                            proposal_id='prop2', primary_optical_element='V', public_date=is_not_public_date)
        FrameFactory.create(configuration_type='SKYFLAT', telescope_id='2m0b', site_id='ogg', instrument_id='fl10',
                            proposal_id='prop3', primary_optical_element='B', public_date=is_public_date)

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
        response = self.client.get(reverse('frame-aggregate') + '?aggregate_field=site_id')
        self.assertEqual(set(response.json()['obstypes']), set([]))
        self.assertEqual(set(response.json()['telescopes']), set([]))
        self.assertEqual(set(response.json()['sites']), set(['bpl', 'coj', 'ogg']))
        self.assertEqual(set(response.json()['instruments']), set([]))
        self.assertEqual(set(response.json()['filters']), set([]))
        self.assertEqual(set(response.json()['proposals']), set([]))

    def test_frame_aggregate_single_field_filtered(self):
        response = self.client.get(reverse('frame-aggregate') + '?INSTRUME=en05&aggregate_field=primary_optical_element')
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
