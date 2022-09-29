from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from ocs_authentication.auth_profile.models import AuthProfile
import requests
import logging

from archive.frames.utils import get_cached_frames_aggregates

logger = logging.getLogger()


def get_all_proposals():
    all_aggregates = get_cached_frames_aggregates()
    if all_aggregates:
        return all_aggregates.get("proposals", [])

    return []

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, default='')
    refresh_token = models.CharField(max_length=255, default='')

    @property
    def proposals(self):
        if self.user.is_superuser:
            proposals = get_all_proposals()
        else:
            cache_key = '{0}_proposals'.format(self.user.id)
            proposals = cache.get(cache_key)
            if not proposals:
                proposals = []
                # TODO: Remove the bearer token fallback once we have deprecated their use
                try:
                    authprofile = AuthProfile.objects.get(user=self.user)
                    response = requests.get(
                        settings.OCS_AUTHENTICATION['OAUTH_PROFILE_URL'],
                        headers={'Authorization': 'Token {}'.format(authprofile.api_token)}
                    )
                except AuthProfile.DoesNotExist:
                    response = requests.get(
                        settings.OCS_AUTHENTICATION['OAUTH_PROFILE_URL'],
                        headers={'Authorization': 'Bearer {}'.format(self.access_token)}
                    )
                if response.status_code == 200:
                    proposals = [proposal['id'] for proposal in response.json()['proposals']]
                else:
                    logger.warning(
                        'User api token was invalid!',
                        extra={'tags': {'username': self.user.username}}
                    )
                cache.set(cache_key, proposals, 3600)
        return proposals


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
