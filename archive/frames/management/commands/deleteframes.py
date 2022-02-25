from datetime import timedelta, date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from archive.frames.models import Frame
import logging
logger = logging.getLogger()

DELETE_BATCH = 1000


class Command(BaseCommand):
    help = "Delete frames that match query parameters supplied by the caller"

    def add_arguments(self, parser):
        parser.add_argument('--days-old', type=int, required=False,
                            help='Frames with observation_date older than days-old will be deleted')
        parser.add_argument('--start', type=date.fromisoformat, required=False,
                            help='Frames newer than start isoformat date will be deleted. Acts on observation_day. Must be specified along with end')
        parser.add_argument('--end', type=date.fromisoformat, required=False,
                            help='Frames older than end isoformat date will be deleted. Acts on observation_day. Must be specified along with start')
        parser.add_argument('--reduction-level', type=int, required=False,
                            help='Only frames with the specified reduction level will be deleted')
        parser.add_argument('--request-id', type=int, required=False,
                            help='Only frames with the specified request id will be deleted')
        parser.add_argument('--observation-id', type=int, required=False,
                            help='Only frames with the specified observation id will be deleted')
        parser.add_argument('--site', type=str, required=False,
                            help='Only frames with the specified site code will be deleted')
        parser.add_argument('--telescope', type=str, required=False,
                            help='Only frames with the specified telescope code will be deleted')
        parser.add_argument('--exclude-types', nargs='*', required=False,
                            help='Exclude these configuration types from the query')
        parser.add_argument('--include-types', nargs='*', required=False,
                            help='Include these configuration types in the query')
        parser.add_argument('--exclude-proposals', nargs='*', required=False,
                            help='Exclude these proposal ids from the query')
        parser.add_argument('--include-proposals', nargs='*', required=False,
                            help='Include these proposal ids in the query')
        parser.add_argument('--exclude-instruments', nargs='*', required=False,
                            help='Exclude these instrument codes from the query')
        parser.add_argument('--include-instruments', nargs='*', required=False,
                            help='Include these instrument codes in the query')

    def handle(self, *args, **options):
        frames = Frame.objects.all().using('default')
        if options['days_old'] and (options['start'] and options['end']):
            raise CommandError("Cannot specify both --days-old days and --start and --end isoformat dates, exiting.")
        if options['days_old']:
            logger.warning(f"Filtering by {options['days_old']} days old")
            frames = frames.filter(observation_date__lt=timezone.now() - timedelta(days=options['days_old']))
        elif options['start'] and options['end']:
            frames = frames.filter(observation_day__lt=options['end'], observation_day__gt=options['start'])
        else:
            raise CommandError("Must specify one of --days-old days or both --start and --end isoformat dates, exiting.")
        if options['reduction_level']:
            frames = frames.filter(reduction_level=options['reduction_level'])
        if options['request_id']:
            frames = frames.filter(request_id=options['request_id'])
        if options['observation_id']:
            frames = frames.filter(observation_id=options['observation_id'])
        if options['site']:
            frames = frames.filter(site_id__iexact=options['site'])
        if options['telescope']:
            frames = frames.filter(telescope_id__iexact=options['telescope'])
        if options['include_types']:
            logger.warning(f"Filtering by include types {','.join(options['include_types'])}")
            frames = frames.filter(configuration_type__in=options['include_types'])
        if options['include_proposals']:
            frames = frames.filter(proposal_id__in=options['include_proposals'])
        if options['include_instruments']:
            frames = frames.filter(instrument_id__in=options['include_instruments'])
        if options['exclude_types']:
            frames = frames.exclude(configuration_type__in=options['exclude_types'])
        if options['exclude_proposals']:
            frames = frames.exclude(proposal_id__in=options['exclude_proposals'])
        if options['exclude_instruments']:
            logger.warning(f"Filtering by exclude instruments {','.join(options['exclude_instruments'])}")
            frames = frames.exclude(instrument_id__in=options['exclude_instruments'])

        logger.warning(frames.query)

        while frames.count() > 0:
            pks_to_delete = frames.values_list('pk', flat=True)[:DELETE_BATCH]
            delete_results = Frame.objects.filter(pk__in=pks_to_delete).delete()
            for key, val in delete_results[1].items():
                logger.info(f"Deleted {val} instances of {key}")
