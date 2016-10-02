from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger()


class Command(BaseCommand):
    def handle(self, *args, **options):
        logger.info('Purging quicklook data')
        Frame.objects.filter(RLEVEL=10, DATE_OBS__lt=timezone.now() - timedelta(days=7)).delete()
        Frame.objects.filter(RLEVEL=11, DATE_OBS__lt=timezone.now() - timedelta(days=7)).delete()
