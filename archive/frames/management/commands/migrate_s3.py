from django.core.management.base import BaseCommand
from django.conf import settings
from archive.frames.models import Frame, Version
from archive.frames.utils import get_s3_client
from botocore.exceptions import ClientError

import logging
import os
import time
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Migrates a set of frames from one s3 bucket to another'

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site', type=str, default='all',
                            help='SITEID to perform frame migrations for, defaults to all sites')
        parser.add_argument('-n', '--num_frames', type=int, default=1,
                            help='The number of frames to migrate. Defaults to 1.')
        parser.add_argument('-d', '--delete', dest='delete', action='store_true', default=False,
                            help='If set, will delete all successfully migrated files as it goes.')

    def handle(self, *args, **options):
        logging.info(f"Beggining Migration of {options['num_frames']} frames for site: {options['site']}")
        if options['delete']:
            logging.info(f"Files will be deleted after they are migrated")
        # Overrite the environment variable AWS credentials with one specially made for this copy operation
        client = get_s3_client(access_key_override=settings.NEW_AWS_ACCESS_KEY_ID,
                               secret_key_override=settings.NEW_AWS_SECRET_ACCESS_KEY)
        frames = Frame.objects.filter(version__migrated=False)
        if options['site'].lower() != 'all':
            frames = frames.filter(SITEID=options['site'].lower())
        frames = frames.distinct()[:options['num_frames']]
        num_frames = 0
        num_files_processed = 0
        start = time.time()
        for frame in frames:
            num_frames += 1
            logging.info(f"Processing frame {frame.id}")
            if frame.DATE_OBS.replace(tzinfo=None) > (datetime.utcnow() - timedelta(days=60)):
                storage = 'STANDARD'
            else:
                storage = 'STANDARD_IA'

            versions = frame.version_set.all().order_by('created')
            for version in versions:
                logging.info(f"  Processing Version {version.key} - {version.created}")
                data_params = version.data_params
                try:
                    response = client.copy_object(CopySource=data_params, Bucket=settings.NEW_BUCKET,
                                                  Key=frame.s3_daydir_key, StorageClass=storage)
                    if 'VersionId' in response and 'CopyObjectResult' in response and 'ETag' in response['CopyObjectResult']:
                        # The md5 looks like it doesn't change, but it would be bad if it did and we didn't update that
                        version.key = response['VersionId']
                        version.migrated = True
                        version.md5 = response['CopyObjectResult']['ETag'].strip('"')
                        version.save()
                        if options['delete']:
                            client.delete_object(**data_params)
                        num_files_processed += 1
                    else:
                        logging.error(f"S3 Copy of frame {frame.id} version {version.key} failed to receive updated metadata")
                except ClientError as e:
                    logging.error(f"S3 Copy of frame {frame.id} version {version.key} Failed to copy: {repr(e)}")
        end = time.time()
        logging.info(f"Finished processing {num_files_processed} files from {num_frames} frames")
        time_per_object = (end - start) / num_files_processed if num_files_processed > 0 else 0
        logging.info(f"Time per object = {time_per_object} seconds")
