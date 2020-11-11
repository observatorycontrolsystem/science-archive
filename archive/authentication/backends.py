from django.contrib.auth.models import User
from archive.authentication.models import Profile
from django.conf import settings
from rest_framework import authentication, exceptions
import requests


class OAuth2Backend(object):
    """
    Authenticate against the Oauth backend, using
    grant_type: password
    """

    def authenticate(self, request, username=None, password=None):
        if username == 'eng':
            return None  # disable eng account
        response = requests.post(
            settings.OAUTH_CLIENT['TOKEN_URL'],
            data={
                'grant_type': 'password',
                'username': username,
                'password': password,
                'client_id': settings.OAUTH_CLIENT['CLIENT_ID'],
                'client_secret': settings.OAUTH_CLIENT['CLIENT_SECRET']
            }
        )
        if response.status_code == 200:
            user, _ = User.objects.get_or_create(username=username)
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


class BearerAuthentication(authentication.BaseAuthentication):
    """
    Allows users to authenticate using the bearer token recieved from
    the odin auth server
    """
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if 'Bearer' not in auth_header:
            return None

        bearer = auth_header.split('Bearer')[1].strip()
        response = requests.get(
            settings.OAUTH_CLIENT['PROFILE_URL'],
            headers={'Authorization': 'Bearer {}'.format(bearer)}
        )

        if not response.status_code == 200:
            raise exceptions.AuthenticationFailed('No Such User')

        user, _ = User.objects.get_or_create(username=response.json()['email'])
        Profile.objects.update_or_create(
            user=user,
            defaults={
                'access_token': bearer,
            }
        )
        return (user, None)
