from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from datetime import datetime
import logging

logger = logging.getLogger()


class Command(BaseCommand):
    def handle(self, *args, **options):
        logger.info('Purging quicklook data')
        Frame.objects.filter(RLEVEL=10, DATE_OBS__lt=datetime.utcnow() - timedelta(days=7)).delete()
        Frame.objects.filter(RLEVEL=11, DATE_OBS__lt=datetime.utcnow() - timedelta(days=7)).delete()
