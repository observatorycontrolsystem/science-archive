from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger()


class Command(BaseCommand):
    help = "Delete frames older than a certain number of days, specified by the caller."

    def add_arguments(self, parser):
        parser.add_argument('frame_expiry_days', type=int,
                            help='Frames older than frame_expiry_days will be purged.')
        parser.add_argument('--delete-bpms', action='store_true',
                            help='Delete BPMs when purging data')

    def handle(self, *args, **options):
        frame_expiry_days = options['frame_expiry_days']
        logger.info(f"Purging frames older than {frame_expiry_days} days.")
        if options['delete_bpms']:
            Frame.objects.filter(DATE_OBS__lt=timezone.now() - timedelta(days=frame_expiry_days)).delete()
        else:
            Frame.objects.filter(DATE_OBS__lt=timezone.now() - timedelta(days=frame_expiry_days)).exclude(OBSTYPE='BPM').delete()



