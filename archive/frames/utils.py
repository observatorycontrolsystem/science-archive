import boto3
import io
import logging
import subprocess
from functools import lru_cache
from django.conf import settings
from django.urls import reverse

from kombu.connection import Connection
from kombu import Exchange

from archive.frames.exceptions import FunpackError

logger = logging.getLogger()


@lru_cache(maxsize=1)
def get_s3_client():
    config = boto3.session.Config(signature_version='s3v4')
    return boto3.client('s3', endpoint_url=settings.S3_ENDPOINT_URL, config=config)


def remove_dashes_from_keys(dictionary):
    new_dictionary = {}
    for k in dictionary:
        new_key = k.replace('-', '_')
        new_dictionary[new_key] = dictionary[k]
    return new_dictionary


def fits_keywords_only(dictionary):
    new_dictionary = {}
    for k in dictionary:
        if k[0].isupper():
            new_dictionary[k] = dictionary[k]
    return new_dictionary


def archived_queue_payload(dictionary, frame):
    new_dictionary = dictionary.copy()
    new_dictionary['filename'] = frame.filename
    new_dictionary['frameid'] = frame.id
    return new_dictionary


def post_to_archived_queue(payload):
    if settings.PROCESSED_EXCHANGE_ENABLED:
        retry_policy = {
            'interval_start': 0,
            'interval_step': 1,
            'interval_max': 4,
            'max_retries': 5,
        }
        processed_exchange = Exchange(settings.PROCESSED_EXCHANGE_NAME, type='fanout')
        with Connection(settings.QUEUE_BROKER_URL, transport_options=retry_policy) as conn:
            producer = conn.Producer(exchange=processed_exchange)
            producer.publish(payload, delivery_mode='persistent', retry=True, retry_policy=retry_policy)


def build_nginx_zip_text(frames, directory, uncompress=False):
    '''
    Build a text document in the format required by the NGINX mod_zip module
    so that NGINX will automatically build and stream a ZIP file to the client.

    For more information, please refer to:
    https://www.nginx.com/resources/wiki/modules/zip/

    @frames: a List of Frame objects
    @directory: the directory within the ZIP file to place the files
    @uncompress: automatically uncompress the files for the client

    @return: text document in NGINX mod_zip format
    '''
    logger.info(msg=f'Building nginx zip text for frames {frames} with uncompress flag {uncompress}')

    client = get_s3_client()
    ret = []

    for frame in frames:
        # retrieve the database record for the Version we will fetch
        version = frame.version_set.first()

        extension = version.extension
        size = version.size
        # if the user requested that we uncompress the files, then redirect .fits.fz
        # files through our transparent funpacker
        logger.info(msg=f'Checking the extension {extension} for version {version}')
        if uncompress and extension == '.fits.fz':
            logger.info(msg='Adding compressed fits file to manifest')
            # The NGINX mod_zip module requires that the files which are used to build the
            # ZIP file must be loaded from an internal NGINX location. Replace the leading
            # portion of the generated URL with an internal NGINX location which proxies all
            # traffic to AWS S3.
            # funpack location (return decompressed files from AWS S3 Bucket)
            location = reverse('s3-funpack-funpack', kwargs={'pk': version.id})
            extension = '.fits'

            # In order to build the manifest for mod_zip, we need to get the uncompressed file size. This is
            # inefficient, but simple.

            with io.BytesIO() as fileobj:
                # download from AWS S3 into an in-memory object
                client.download_fileobj(Bucket=version.data_params['Bucket'],
                                        Key=version.data_params['Key'],
                                        Fileobj=fileobj)
                fileobj.seek(0)

                cmd = ['/usr/bin/funpack', '-C', '-S', '-', ]
                try:
                    proc = subprocess.run(cmd, input=fileobj.getvalue(), stdout=subprocess.PIPE)
                    proc.check_returncode()
                    size = len(bytes(proc.stdout))
                except subprocess.CalledProcessError as cpe:
                    logger.error(f'funpack failed with return code {cpe.returncode} and error {cpe.stderr}')
                    raise FunpackError

        else:
            # The NGINX mod_zip module requires that the files which are used to build the
            # ZIP file must be loaded from an internal NGINX location. Replace the leading
            # portion of the generated URL with an internal NGINX location which proxies all
            # traffic to AWS S3.
            # default location (return files as-is from AWS S3 Bucket)
            params = {
                'Key': version.s3_daydir_key,
                'Bucket': settings.BUCKET,
            }
            url = client.generate_presigned_url('get_object', Params=params, ExpiresIn=86400)
            location = url.replace(f'https://{settings.BUCKET}.s3.amazonaws.com', '/s3-native')

        # The NGINX mod_zip module builds ZIP files using a manifest. Build the manifest
        # line for this frame.
        line = f'- {size} {location} {directory}/{frame.basename}{extension}\n'
        # Add to returned lines
        ret.append(line)

    logger.info(msg=f'Returning manifests: {ret}')

    # Concatenate all lines together into a single string
    return ''.join(ret)
