from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from archive.frames.models import Frame

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
        frames = Frame.objects.filter(DATE_OBS__lt=timezone.now() - timedelta(days=frame_expiry_days))
        if not options['delete_bpms']:
            frames = frames.exclude(OBSTYPE='BPM')
        frames.delete()
