from archive.test_helpers import ReplicationTestCase
from unittest.mock import patch
from archive.authentication.models import Profile
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
import json
import responses


class TestUserView(ReplicationTestCase):
    @patch('requests.get')
    @patch('requests.post')
    def setUp(self, post_mock, get_mock):
        self.normal_user = User.objects.create(username='frodo')
        self.normal_user.backend = settings.AUTHENTICATION_BACKENDS[0]
        Profile.objects.create(user=self.normal_user)

    @responses.activate
    def test_user_view(self):
        responses.add(
            responses.GET,
            settings.OAUTH_CLIENT['PROFILE_URL'],
            body=json.dumps({'proposals': [{'id': 'TestProposal'}]}),
            status=200,
            content_type='application/json'
        )
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'TestProposal')
        self.assertEqual(response.json()['username'], self.normal_user.username)

    def test_anonymous_user_view(self):
        response = self.client.get(reverse('profile'))
        self.assertFalse(response.json()['username'])
        self.assertFalse(response.json()['profile'])
