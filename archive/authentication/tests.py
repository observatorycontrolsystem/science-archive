from django.contrib.auth.models import User
from django.conf import settings
from unittest.mock import patch
from archive.authentication.models import Profile
import responses
from django.test import TestCase
import json


class TestAuthentication(TestCase):
    @patch('requests.get')
    @patch('requests.post')
    def setUp(self, post_mock, get_mock):
        self.admin_user = User.objects.create_superuser('admin', 'admin@lcgot.net', 'password')
        self.normal_user = User.objects.create(username='frodo')
        Profile.objects.create(user=self.normal_user)

    @patch('requests.get')
    @patch('requests.post')
    def test_model_backend(self, post_mock, get_mock):
        self.assertTrue(self.client.login(username='admin', password='password'))
        self.assertFalse(get_mock.called)

    @responses.activate
    def test_oauth_backend_success(self):
        responses.add(
            responses.POST,
            settings.ODIN_OAUTH_CLIENT['TOKEN_URL'],
            body=json.dumps({'access_token': 'test_access', 'refresh_token': 'test_refresh'}),
            status=200,
            content_type='application/json'
        )
        self.assertTrue(self.client.login(username='testuser', password='password'))
        u = User.objects.get(username='testuser')
        self.assertEqual(u.profile.access_token, 'test_access')
        self.assertEqual(u.profile.refresh_token, 'test_refresh')
        self.assertTrue(u.auth_token)

        # Test relog
        self.client.logout()
        self.assertTrue(self.client.login(username='testuser', password='password'))

    @responses.activate
    def test_oauth_backend_failure(self):
        responses.add(
            responses.POST,
            settings.ODIN_OAUTH_CLIENT['TOKEN_URL'],
            body=json.dumps({'non_field_errors': 'Unable to log in with provided credentials'}),
            status=400,
            content_type='application/json'
        )
        self.assertFalse(self.client.login(username='testuser', password='password'))
        self.assertFalse(User.objects.filter(username='testuser').exists())

    @responses.activate
    def test_proposals(self):
        responses.add(
            responses.GET,
            settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
            body=json.dumps([{'code': 'TestProposal'}]),
            status=200,
            content_type='application/json'
        )
        self.assertIn('TestProposal', self.normal_user.profile.proposals)

    @responses.activate
    def test_proposals_bad_token(self):
        responses.add(
            responses.GET,
            settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
            body=json.dumps({'error': 'Bad credentials'}),
            status=401,
            content_type='application/json'
        )
        self.assertFalse(self.normal_user.profile.proposals)
