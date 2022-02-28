from django.contrib.auth.models import User
from archive.authentication.models import Profile
from django.conf import settings
from rest_framework import authentication, exceptions
from ocs_authentication.auth_profile.models import AuthProfile
import requests


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
            settings.OCS_AUTHENTICATION['OAUTH_PROFILE_URL'],
            headers={'Authorization': 'Bearer {}'.format(bearer)}
        )

        if not response.status_code == 200:
            raise exceptions.AuthenticationFailed('No Such User')

        profile = response.json()
        user, _ = User.objects.get_or_create(username=profile['username'])
        Profile.objects.update_or_create(
            user=user,
            defaults={
                'access_token': bearer,
            }
        )
        AuthProfile.objects.update_or_create(user=user,
            defaults={
                'staff_view': profile.get('profile', {}).get('staff_view', False),
                'api_token': profile.get('tokens', {}).get('api_token')
            }
        )

        return (user, None)
