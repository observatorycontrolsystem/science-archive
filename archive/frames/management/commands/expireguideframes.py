from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from django.utils import timezone
import logging
import os


logger = logging.getLogger()

def get_tuple_from_environment(variable_name, default):
    return tuple(os.getenv(variable_name, default).strip(',').replace(' ', '').split(','))


GUIDE_CAMERAS_TO_PERSIST = get_tuple_from_environment(
    'GUIDE_CAMERAS_TO_PERSIST',
    'kb42,kb38,ak01,ak02,ak03,ak04,ak05,ak06,ak07,ak11,ak12'
)

class Command(BaseCommand):
    def handle(self, *args, **options):
        expiration_date = timezone.now() - timedelta(days=365)
        logger.info(f'Expiring imager guide frames from before {expiration_date.isoformat()}')

        old_guide_frames = Frame.objects.filter(DATE_OBS__lte=expiration_date, OBSTYPE='GUIDE').exclude(
            INSTRUME__in=GUIDE_CAMERAS_TO_PERSIST).delete()
