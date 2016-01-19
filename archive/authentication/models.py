from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
import requests


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, default='')
    refresh_token = models.CharField(max_length=255, default='')
    proposals = ArrayField(models.CharField(max_length=255, blank=True), default=list())


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


@receiver(post_save, sender=Profile)
def set_proposals(sender, instance=None, created=False, **kwargs):
    response = requests.get(
        settings.ODIN_OAUTH_CLIENT['PROPOSALS_URL'],
        headers={'Authorization': 'Bearer {}'.format(instance.access_token)}
    ).json()
    proposals = [proposal['code'] for proposal in response]
    Profile.objects.filter(user=instance.user).update(proposals=proposals)
