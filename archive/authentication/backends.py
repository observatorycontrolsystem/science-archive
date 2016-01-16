from django.contrib.auth.models import User
from archive.authentication.models import Profile
from django.conf import settings
import requests


class OAuth2Backend(object):
    """
    Authenticate against the Oauth backend, using
    grant_type: password
    """

    def authenticate(self, username=None, password=None):

        response = requests.post(
            settings.ODIN_OAUTH_CLIENT['TOKEN_URL'],
            data={
                'grant_type': 'password',
                'username': username,
                'password': password,
                'client_id': settings.ODIN_OAUTH_CLIENT['CLIENT_ID'],
                'client_secret': settings.ODIN_OAUTH_CLIENT['CLIENT_SECRET']
            }
        )
        if response.status_code == 200:
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']
            proposals = requests.get(
                settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
                headers={'Authorization': 'Bearer {}'.format(access_token)}
            ).json()
            try:
                user = User.objects.get(username=username)
                profile = user.profile
            except User.DoesNotExist:
                user = User(username=username)
                user.save()
                profile, created = Profile.objects.get_or_create(user=user)
            profile.access_token = access_token
            profile.refresh_token = refresh_token
            profile.proposals = [proposal['code'] for proposal in proposals]
            profile.save()
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
