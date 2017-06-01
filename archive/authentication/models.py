from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from rest_framework.authtoken.models import Token
import requests
import logging

from archive.frames.models import Frame

logger = logging.getLogger()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, default='')
    refresh_token = models.CharField(max_length=255, default='')

    @property
    def proposals(self):
        cache_key = '{0}_proposals'.format(self.user.id)
        cached_proposals = cache.get(cache_key)
        if not cached_proposals:
            if self.user.is_superuser:
                proposals = [
                    i[0] for i in Frame.objects.all()
                                               .order_by().values_list('PROPID')
                                               .distinct() if i[0]
                ]
            else:
                proposals = []
                response = requests.get(
                    settings.ODIN_OAUTH_CLIENT['PROFILE_URL'],
                    headers={'Authorization': 'Bearer {}'.format(self.access_token)}
                )
                if response.status_code == 200:
                    proposals = [proposal['id'] for proposal in response.json()['proposals']]
                else:
                    # TODO implement getting new token via refresh token
                    # As of this writing tokens never expire in Odin
                    logger.warn(
                        'User auth token was invalid!',
                        extra={'tags': {'username': self.user.username}}
                    )
            cache.set(cache_key, proposals, 3600)
            return proposals
        return cached_proposals


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
