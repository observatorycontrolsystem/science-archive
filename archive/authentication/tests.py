from django.contrib.auth.models import User
from django.conf import settings
from unittest.mock import patch
from archive.authentication.models import Profile
from archive.frames.tests.factories import FrameFactory
from archive.test_helpers import ReplicationTestCase
from archive.frames.utils import aggregate_raw_sql, set_cached_aggregates
from archive.frames.models import Frame
from rest_framework.test import APITestCase
from ocs_authentication.auth_profile.models import AuthProfile
from django.urls import reverse
import responses
import json



class TestRevokeTokenAPI(APITestCase):
    def setUp(self) -> None:
        super(TestRevokeTokenAPI, self).setUp()
        self.user = User.objects.create(username='test_revoke_token_user')
        Profile.objects.get_or_create(user=self.user)
        AuthProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_revoke_token(self):
        initial_token = self.user.auth_token
        response = self.client.post(reverse('revoke_api_token'))
        self.assertContains(response, 'API token revoked', status_code=200)
        self.user.refresh_from_db()
        self.assertNotEqual(initial_token, self.user.auth_token)

    def test_unauthenticated(self):
        self.client.logout()
        initial_token = self.user.auth_token
        response = self.client.post(reverse('revoke_api_token'))
        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(initial_token, self.user.auth_token)

class TestAuthentication(ReplicationTestCase):
    @patch('requests.get')
    @patch('requests.post')
    def setUp(self, post_mock, get_mock):
        self.admin_user = User.objects.create_superuser('admin', 'admin@lcgot.net', 'password')
        self.normal_user = User.objects.create(username='frodo')
        Profile.objects.get_or_create(user=self.normal_user)
        AuthProfile.objects.create(user=self.normal_user)
        Profile.objects.get_or_create(user=self.admin_user)
        AuthProfile.objects.create(user=self.admin_user)

    @patch('requests.get')
    @patch('requests.post')
    def test_model_backend(self, post_mock, get_mock):
        self.assertTrue(self.client.login(username='admin', password='password'))
        self.assertFalse(get_mock.called)

    @responses.activate
    def test_proposals(self):
        responses.add(
            responses.GET,
            settings.OCS_AUTHENTICATION['OAUTH_PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'TestProposal'}]}),
            status=200,
            content_type='application/json'
        )
        self.assertIn('TestProposal', self.normal_user.profile.proposals)

    @responses.activate
    def test_proposals_bad_token(self):
        responses.add(
            responses.GET,
            settings.OCS_AUTHENTICATION['OAUTH_PROFILE_URL'],
            body=json.dumps({'error': 'Bad credentials'}),
            status=401,
            content_type='application/json'
        )
        self.assertFalse(self.normal_user.profile.proposals)

    @patch('requests.get')
    @patch('requests.post')
    def test_superuser_all_proposals(self, post_mock, get_mock):
        self.admin_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        self.client.force_login(self.admin_user)
        FrameFactory.create(proposal_id='prop1')
        FrameFactory.create(proposal_id='prop2')

        # mimic a cache update from the cacheaggregations mgmt command
        set_cached_aggregates(aggregate_raw_sql(Frame.objects.all()))

        self.assertCountEqual(['prop1', 'prop2'], self.admin_user.profile.proposals)
        self.assertFalse(get_mock.called)
