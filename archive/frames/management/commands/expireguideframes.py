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
MAX_TO_DELETE = 10000

class Command(BaseCommand):
    help = 'Deletes guide frames older than 1 year for imagers'

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site', type=str, default='all',
                            help='SITEID to delete guide frames for. Default is all sites.')
        parser.add_argument('-m', '--max_delete', type=int, default=MAX_TO_DELETE,
                            help='Max number of frames to delete. Default is 10,000.')

    def handle(self, *args, **options):
        expiration_date = timezone.now() - timedelta(days=365)
        logger.info(f"Expiring up to {options['max_delete']} imager guide frames from before {expiration_date.isoformat()} for {options['site']} site(s)")

        guide_frames = Frame.objects.filter(DATE_OBS__lte=expiration_date, OBSTYPE='GUIDE').exclude(
            INSTRUME__in=GUIDE_CAMERAS_TO_PERSIST)
        if options['site'].lower() != 'all':
            guide_frames = guide_frames.filter(SITEID=options['site'].lower())

        delete_results = Frame.objects.filter(pk__in=guide_frames.values_list('pk', flat=True)[:options['max_delete']]).delete()

        for key, val in delete_results[1].items():
            logger.info(f"Deleted {val} instances of {key}")
