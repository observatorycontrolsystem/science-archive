from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.utils.functional import cached_property
import requests
import logging

logger = logging.getLogger()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, default='')
    refresh_token = models.CharField(max_length=255, default='')

    @cached_property
    def proposals(self):
        response = requests.get(
            settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
            headers={'Authorization': 'Bearer {}'.format(self.access_token)}
        )
        if response.status_code == 200:
            return [proposal['code'] for proposal in response.json()]
        else:
            # TODO implement getting new token via refresh token
            # As of this writing tokens never expire in Odin
            logger.warn(
                'User auth token was invalid!',
                extra={'tags': {'username': self.user.username}}
            )
            return []


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
