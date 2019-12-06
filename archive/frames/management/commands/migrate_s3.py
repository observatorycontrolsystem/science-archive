from django.core.management.base import BaseCommand
from archive.frames.models import Frame, Version
from archive.frames.utils import get_s3_client
from botocore.exceptions import ClientError
from django.conf import settings

import logging

FRAME_LIMIT = 1

class Command(BaseCommand):
    def handle(self, *args, **options):
        client = get_s3_client()
        frames = Frame.objects.filter(version_set__migrated=False).distinct()[:FRAME_LIMIT]
        for frame in frames:
            logging.info(f"Processing frame {frame.id}")
            s3_path = frame.s3_key
            versions = Version.objects.filter(frame=frame).order_by('created')
            for version in versions:
                logging.info(f"  Processing Version {version.key} - {version.created}")
                try:
                    response = client.copy_object(CopySource=version.data_params, Bucket=settings.NEW_BUCKET,
                                                  Key=frame.s3_daydir_key)
                    if 'VersionId' in response and 'CopyObjectResult' in response and 'ETAG' in response['CopyObjectResult']:
                        version.update(
                            key=response['VersionId'],
                            migrated=True,
                            md5=response['CopyObjectResult']['ETag'].strip('"'))
                    else:
                        logging.error(f"S3 Copy of frame {frame.id} version {version.key} failed to receive updated metadata")
                except ClientError as e:
                    logging.error(f"S3 Copy of frame {frame.id} version {version.key} Failed to copy: {repr(e)}")
