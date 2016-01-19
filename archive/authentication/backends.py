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
            user, created = User.objects.get_or_create(username=username)
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    'access_token': response.json()['access_token'],
                    'refresh_token': response.json()['refresh_token']
                }
            )
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
