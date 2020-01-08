from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from archive.frames.models import Frame, Version
from archive.frames.utils import get_s3_client
from botocore.exceptions import ClientError
from astropy.io import fits

import logging
import os
import io
from contextlib import closing
import time
from datetime import timedelta


def pack(uncompressed_hdulist: fits.HDUList) -> fits.HDUList:
    if uncompressed_hdulist[0].data is None:
        primary_hdu = fits.PrimaryHDU(header=uncompressed_hdulist[0].header)
        hdulist = [primary_hdu]
    else:
        primary_hdu = fits.PrimaryHDU()
        compressed_hdu = fits.CompImageHDU(data=uncompressed_hdulist[0].data, header=uncompressed_hdulist[0].header,
                                           quantize_level=64, quantize_method=1)
        hdulist = [primary_hdu, compressed_hdu]

    for hdu in uncompressed_hdulist[1:]:
        if isinstance(hdu, fits.ImageHDU):
            compressed_hdu = fits.CompImageHDU(data=hdu.data, header=hdu.header,
                                               quantize_level=64, quantize_method=1)
            hdulist.append(compressed_hdu)
        else:
            hdulist.append(hdu)
    return fits.HDUList(hdulist)


def copy_version(version, client, storage_class, frame_id, should_delete=False):
    data_params = version.data_params
    try:
        response = client.copy_object(CopySource=data_params, Bucket=settings.NEW_BUCKET,
                                      Key=version.s3_daydir_key, StorageClass=storage_class)
    except ClientError as ce:
        logging.error(f"S3 Copy of frame {frame_id} version {version.key} Failed to copy: {repr(ce)}")
        return False
    if 'VersionId' in response and 'CopyObjectResult' in response and 'ETag' in response['CopyObjectResult']:
        # The md5 looks like it doesn't change, but it would be bad if it did and we didn't update that
        version.key = response['VersionId']
        version.migrated = True
        version.md5 = response['CopyObjectResult']['ETag'].strip('"')
        version.save()
        try:
            if should_delete:
                client.delete_object(**data_params)
        except ClientError as ce:
            logging.warning(f"S3 Delete of old frame key {data_params['Key']} version {data_params['VersionId']} in bucket {data_params['Bucket']} Failed: {repr(ce)}")
    else:
        logging.error(f"S3 Copy of frame {frame_id} version {version.key} failed to receive updated metadata")
        return False
    return True

def fpack_version(version, client, storage_class, frame_id, should_delete=False):
    data_params = version.data_params
    try:
        file_response = client.get_object(**data_params)
    except ClientError as ce:
        logging.error(f"S3 Get of frame {frame_id} version {version.key} Failed: {repr(ce)}")
        return False
    base_file = file_response['Body']
    with closing(base_file):
        # need to convert StreamingBody to BytesIO for astropy to use as input
        input_file = io.BytesIO(base_file.read())
    fits_file = fits.open(input_file)
    filename = f'{version.frame.basename}.fits.fz'
    content_disposition = f'attachment; filename={filename}'
    content_type = '.fits.fz'
    fpack_file = io.BytesIO()
    setattr(fpack_file, 'name', filename)
    # This works with non-fpacked data in LCO's past, but it doesn't work with funpack fpacked data
    compressed_hdulist = pack(fits_file)
    compressed_hdulist.writeto(fpack_file)
    fpack_file.seek(0)
    try:
        response = client.put_object(Body=fpack_file, Bucket=settings.NEW_BUCKET,
                                     Key=f'{version.s3_daydir_key}.fz', StorageClass=storage_class)
    except ClientError as ce:
        logging.error(f"S3 Put of fpacked frame {frame_id} version {version.key} Failed: {repr(ce)}")
        return False
    if 'VersionId' in response and 'ETag' in response:
        version.key = response['VersionId']
        version.migrated = True
        version.extension = '.fits.fz'
        version.md5 = response['ETag'].strip('"')
        version.save()
        try:
            if should_delete:
                client.delete_object(**data_params)
        except ClientError as ce:
            logging.warning(f"S3 Delete of old frame key {data_params['Key']} version {data_params['VersionId']} in bucket {data_params['Bucket']} Failed: {repr(ce)}")
    else:
        logging.error(f"S3 Put of fpacked frame {frame_id} version {version.key} Failed to receive updated metadata")
        return False
    return True


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
        logging.info(f"Beginning Migration of {options['num_frames']} frames for site: {options['site']}")
        if options['delete']:
            logging.info(f"Files will be deleted after they are migrated")
        client = get_s3_client()
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
            if frame.DATE_OBS > (timezone.now() - timedelta(days=60)):
                storage = 'STANDARD'
            else:
                storage = 'STANDARD_IA'

            versions = frame.version_set.all().order_by('extension', 'created')
            successful_fpack = False  # This ensures we only delete fpacked versions if we successfully migrated a non-fpacked one
            extensions = [version.extension for version in versions]
            for version in versions:
                logging.info(f"  Processing Version {version.key} - {version.created}")
                data_params = version.data_params
                # Only fpack .fits versions for files with both .fits and .fz
                if '.fits' in extensions and '.fits.fz' in extensions:
                    # The file is a basic (not fpacked) fits file. We should fpack it first and then send it to S3
                    if version.extension == '.fits':
                        if fpack_version(version, client, storage, frame.id, options['delete']):
                            num_files_processed += 1
                            successful_fpack = True
                    elif options['delete'] and successful_fpack:
                        logging.info(f"  Deleting old fpacked Version {version.key}")
                        client.delete_object(**data_params)
                        version.delete()
                else:
                    if copy_version(version, client, storage, frame.id, options['delete']):
                        num_files_processed += 1

        end = time.time()
        logging.info(f"Finished processing {num_files_processed} files from {num_frames} frames")
        time_per_object = (end - start) / num_files_processed if num_files_processed > 0 else 0
        logging.info(f"Time per object = {time_per_object} seconds")
