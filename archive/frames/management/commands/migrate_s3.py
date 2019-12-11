from django.core.management.base import BaseCommand
from archive.frames.models import Frame, Version
from botocore.exceptions import ClientError

import boto3
import logging
import os
from datetime import datetime, timedelta

FRAME_LIMIT = 1
NEW_AWS_ACCESS_KEY_ID = os.getenv('NEW_AWS_ACCESS_KEY_ID', '')
NEW_AWS_SECRET_ACCESS_KEY = os.getenv('NEW_AWS_SECRET_ACCESS_KEY', '')
NEW_AWS_BUCKET = os.getenv('NEW_AWS_BUCKET', '')


class Command(BaseCommand):
    def handle(self, *args, **options):
        config = boto3.session.Config(region_name='us-west-2', signature_version='s3v4')
        # Overrite the environment variable AWS credentials with one specially made for this copy operation
        client = boto3.client(
            's3',
            config=config,
            aws_access_key_id=NEW_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=NEW_AWS_SECRET_ACCESS_KEY,
        )
        frames = Frame.objects.filter(version_set__migrated=False).distinct()[:FRAME_LIMIT]
        num_frames = frames.count()
        num_files_processed = 0
        for frame in frames:
            logging.info(f"Processing frame {frame.id}")
            if frame.DATE_OBS.replace(tzinfo=None) > (datetime.utcnow() - timedelta(days=60)):
                storage = 'STANDARD'
            else:
                storage = 'STANDARD_IA'

            versions = frame.version_set.all().order_by('created')
            for version in versions:
                logging.info(f"  Processing Version {version.key} - {version.created}")
                try:
                    response = client.copy_object(CopySource=version.data_params, Bucket=NEW_AWS_BUCKET,
                                                  Key=frame.s3_daydir_key, StorageClass=storage)
                    if 'VersionId' in response and 'CopyObjectResult' in response and 'ETAG' in response['CopyObjectResult']:
                        # The md5 looks like it doesn't change, but it would be bad if it did and we didn't update that
                        version.update(
                            key=response['VersionId'],
                            migrated=True,
                            md5=response['CopyObjectResult']['ETag'].strip('"'))
                        num_files_processed += 1
                    else:
                        logging.error(f"S3 Copy of frame {frame.id} version {version.key} failed to receive updated metadata")
                except ClientError as e:
                    logging.error(f"S3 Copy of frame {frame.id} version {version.key} Failed to copy: {repr(e)}")
        logging.info(f"Finished processing {num_files_processed} files from {num_frames} frames")
