from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.core.cache import cache


class Command(BaseCommand):
    def handle(self, *args, **options):
        print(settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES'))
        for user in User.objects.all():
            thr = cache.get('throttle_user_{0}'.format(user.id))
            if thr:
                print('{0}: {1}'.format(user.username, len(thr)))
