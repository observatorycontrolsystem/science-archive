from django.core.management.base import BaseCommand
from archive.frames.models import Frame
from datetime import timedelta
from django.utils import timezone
import logging
import os


logger = logging.getLogger()

def get_tuple_from_environment(variable_name, default):
    return tuple(os.getenv(variable_name, default).strip(',').replace(' ', '').split(','))

# We want to persist guide frames from our spectrograph instruments (Floyds and NRES) indefinitely.
# akXX cameras correspond to NRES autoguiders, and kbXX cameras listed here are floyds guiders
# This list and the corresponding environment variable (if used) MUST be updated when a new
# spectrograph autoguider is added to our network!!!
GUIDE_CAMERAS_TO_PERSIST = get_tuple_from_environment(
    'GUIDE_CAMERAS_TO_PERSIST',
    ''
)
DELETE_BATCH = 1000

class Command(BaseCommand):
    help = """Deletes guide frames older than 1 year for imagers. This script does not check if the version has been replicated
              in s3 before deleting it, however this is unlikely to be a problem given that the versions being deleted are old."""

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site', type=str, default='all',
                            help='site_id to delete guide frames for. Default is all sites.')

    def handle(self, *args, **options):
        expiration_date = timezone.now() - timedelta(days=365)
        logger.info(f"Expiring imager guide frames from before {expiration_date.isoformat()} for {options['site']} site(s)")

        guide_frames = Frame.objects.using('default').filter(observation_date__lte=expiration_date, configuration_type='GUIDE').exclude(
            instrument_id__in=GUIDE_CAMERAS_TO_PERSIST)
        if options['site'].lower() != 'all':
            guide_frames = guide_frames.filter(site_id=options['site'].lower())

        while guide_frames.count() > 0:
            pks_to_delete = guide_frames.values_list('pk', flat=True)[:DELETE_BATCH]
            delete_results = Frame.objects.filter(pk__in=pks_to_delete).delete()
            for key, val in delete_results[1].items():
                logger.info(f"Deleted {val} instances of {key}")
