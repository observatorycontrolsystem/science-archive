from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from django.utils import timezone
import logging
import os


logger = logging.getLogger()

def get_tuple_from_environment(variable_name, default):
    return tuple(os.getenv(variable_name, default).strip(',').replace(' ', '').split(','))


CAMERAS_TO_EXPIRE = get_tuple_from_environment('GUIDE_CAMERAS_TO_EXPIRE', '')

class Command(BaseCommand):
    def handle(self, *args, **options):
        expiration_date = timezone.now() - timedelta(days=365)
        logger.info(f'Expiring imager guide frames from before {expiration_date.isoformat()}')

        old_guide_frames = Frame.objects.filter(DATE_OBS__lte=expiration_date, OBSTYPE='GUIDE',
                                                INSTRUME__in=CAMERAS_TO_EXPIRE).delete()
