import logging
import subprocess
import io
import requests
from urllib.parse import urlsplit, urljoin
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.db import connections
from django.db.models.query import EmptyQuerySet
from astropy.io import fits

from kombu.connection import Connection
from kombu import Exchange

from archive.frames.exceptions import FunpackError

from ocs_archive.input.file import EmptyFile
from ocs_archive.input.filefactory import FileFactory
from ocs_archive.storage.filestorefactory import FileStoreFactory

logger = logging.getLogger()


def get_file_store_path(filename, file_metadata):
    # The file store path can depend on specific info in the filename, which is only available within
    # specific DataFile subclasses based on extension, so this EmptyFile with the filename is needed
    # to be able to build the correct file store path
    empty_file = EmptyFile(filename)
    data_file = FileFactory.get_datafile_class_for_extension(empty_file.extension)(empty_file, file_metadata, {}, {})
    return data_file.get_filestore_path()


def archived_queue_payload(dictionary, frame):
    new_dictionary = dictionary.get('headers').copy()
    new_dictionary['area'] = dictionary.get('area')
    new_dictionary['basename'] = dictionary.get('basename')
    new_dictionary['version_set'] = dictionary.get('version_set')
    new_dictionary['filename'] = frame.filename
    new_dictionary['frameid'] = frame.id
    return new_dictionary


def get_configuration_type_tuples():
    configuration_type_tuples = cache.get('configuration_type_tuples')
    if not configuration_type_tuples:
        configuration_types = set()
        instrument_data = get_configdb_data()
        if instrument_data:
            for instrument in instrument_data:
                for configuration_type in instrument['instrument_type']['configuration_types']:
                    configuration_types.add(configuration_type['code'])
        else:
            configuration_types = set(settings.CONFIGURATION_TYPES)
        configuration_type_tuples = [(conf_type, conf_type) for conf_type in configuration_types]
        cache.set('configuration_type_tuples', configuration_type_tuples, 3600)

    return configuration_type_tuples


def get_configdb_data():
    instrument_data = cache.get('configdb_instrument_data')
    if not instrument_data:
        if settings.CONFIGDB_URL:
            url = urljoin(settings.CONFIGDB_URL, '/instruments/')
            try:
                response = requests.get(url)
                response.raise_for_status()
                instrument_data = response.json()['results']
                cache.set('configdb_instrument_data', instrument_data, 3600)
            except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
                logger.warning(f"Failed to access Configdb at {settings.CONFIGDB_URL}: {repr(e)}")
                instrument_data = []

    return instrument_data


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


def build_nginx_zip_text(frames, directory, uncompress=False, catalog_only=False):
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

    file_store = FileStoreFactory.get_file_store_class()()
    ret = []

    for frame in frames:
        # retrieve the database record for the Version we will fetch
        version = frame.version_set.first()
        path = get_file_store_path(frame.filename, frame.get_header_dict())
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
            # traffic to Filestore URL.
            # funpack location (return decompressed files from FileStore)
            location = reverse('frame-funpack-funpack', kwargs={'pk': frame.id})
            extension = '.fits'

            # In order to build the manifest for mod_zip, we need to get the uncompressed file size. This is
            # inefficient, but simple.
            with file_store.get_fileobj(path) as fileobj:
                cmd = ['/usr/bin/funpack', '-C', '-S', '-', ]
                try:
                    proc = subprocess.run(cmd, input=fileobj.getvalue(), stdout=subprocess.PIPE)
                    proc.check_returncode()
                    size = len(bytes(proc.stdout))
                except subprocess.CalledProcessError as cpe:
                    logger.error(f'funpack failed with return code {cpe.returncode} and error {cpe.stderr}')
                    raise FunpackError
        elif catalog_only and frame.reduction_level == 91 and frame.configuration_type == 'EXPOSE':
            logger.info(msg='Adding catalog to manifest')
            location = reverse('frame-catalog-catalog', kwargs={'pk': frame.id})
            extension = '-catalog.fits'

            with file_store.get_fileobj(path) as fileobj:
                image = fits.open(fileobj)
                try:
                    catalog = image['CAT']
                except KeyError:
                    continue
                with io.BytesIO() as buffer:
                    hdulist = fits.HDUList([fits.PrimaryHDU(header=image['SCI'].header), catalog])
                    hdulist.writeto(buffer)
                    buffer.seek(0)
                    size = buffer.getbuffer().nbytes
        else:
            # The NGINX mod_zip module requires that the files which are used to build the
            # ZIP file must be loaded from an internal NGINX location. Replace the leading
            # portion of the generated URL with an internal NGINX location which proxies all
            # traffic to AWS S3.
            # default location (return files as-is from AWS S3 Bucket)
            url = file_store.get_url(path, version.key, expiration=86400)
            split_url = urlsplit(url)
            url_to_replace = split_url.scheme + "://" + split_url.netloc
            location = url.replace(url_to_replace, '/zip-files')

        # The NGINX mod_zip module builds ZIP files using a manifest. Build the manifest
        # line for this frame.
        line = f'- {size} {location} {directory}/{frame.basename}{extension}\n'
        # Add to returned lines
        ret.append(line)

    logger.info(msg=f'Returning manifests: {ret}')

    # Concatenate all lines together into a single string
    return ''.join(ret)


def aggregate_frames_sql(frames, timeout=0, user_proposals=None):
    if isinstance(frames, EmptyQuerySet):
        return {
            "sites": set(),
            "telescopes": set(),
            "filters": set(),
            "instruments": set(),
            "obstypes": set(),
            "proposals": set(),
            "generated_at": "",
        }

    frames = frames.values_list(
        "proposal_id",
        "configuration_type",
        "site_id",
        "telescope_id",
        "instrument_id",
        "primary_optical_element",
    ).order_by()

    user_proposals_not_none = user_proposals is not None
    user_proposals = user_proposals if user_proposals_not_none else []

    with connections["replica"].cursor() as cursor:
        django_sql, params = frames.query.sql_with_params()
        params = (timeout, ) + params + (user_proposals,)
        query_sql = f"""
          SET LOCAL statement_timeout TO %s;

          -- Disabling sort biases the planner to use HashAggreate which performs
          -- better on large time windows.
          SET LOCAL enable_sort = off;

          -- "WITH" statements are lazy definitions and only executed if needed
          -- by the "real" query further below.
          WITH

          -- SQL as generated by Django's QuerySet w/ any filters applied.
          django AS (
            {django_sql}
          ),

          -- Temporary table for joining
          user_proposals AS (
            SELECT unnest(%s::text[])::text AS proposal_id
          ),

          -- Limiting frames this way performs better than using the IN operator.
          filtered_user_proposals AS(
            SELECT
              proposal_id,
              configuration_type,
              site_id,
              telescope_id,
              instrument_id,
              primary_optical_element
            FROM user_proposals
            JOIN django USING(proposal_id)
          ),

          -- This is being generated dynamically in Python using f-strings.
          filtered AS (
            SELECT
              proposal_id,
              configuration_type,
              site_id,
              telescope_id,
              instrument_id,
              primary_optical_element
            FROM {"filtered_user_proposals" if user_proposals_not_none else "django"}
          ),

          -- First do a distinct across all the elements taken together.
          -- This might seem like an unnecessary step, but whittling down the set
          -- before doing a distinct per column drastically improves performance.
          filtered_distinct AS (
            SELECT DISTINCT
              proposal_id,
              configuration_type,
              site_id,
              telescope_id,
              instrument_id,
              primary_optical_element
            FROM filtered
          )

          -- This is where the query is actually materialized.
          -- Each array_agg takes each row and builds a distinct set for
          -- that column (ignoring any null values or empty strings).
          -- The result is a single row, with each column an array of strings.
          SELECT
            array_agg(DISTINCT proposal_id) FILTER (WHERE proposal_id <> '') AS proposals,
            array_agg(DISTINCT configuration_type) FILTER (WHERE configuration_type <> '') AS obstypes,
            array_agg(DISTINCT site_id)  FILTER (WHERE site_id <> '')AS sites,
            array_agg(DISTINCT telescope_id) FILTER (WHERE telescope_id <> '') AS telescopes,
            array_agg(DISTINCT instrument_id) FILTER (WHERE instrument_id <> '') AS instruments,
            array_agg(DISTINCT primary_optical_element) FILTER (WHERE primary_optical_element <> '') AS filters,
            to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MSZ') AS generated_at
          FROM filtered_distinct;
        """ # nosec B608
        logger.debug("executing aggregate query: %s (params: %s)", query_sql, params)
        cursor.execute(query_sql, params)
        row = cursor.fetchone()

    return {
        "proposals": set(row[0] or []),
        "obstypes": set(row[1] or []),
        "sites": set(row[2] or []),
        "telescopes": set(row[3] or []),
        "instruments": set(row[4] or []),
        "filters": set(row[5] or []),
        "generated_at": row[6],
    }



ALL_FRAMES_AGGREGATES_CACHE_KEY = "all_frames_aggregates"

def get_cached_frames_aggregates():
    return cache.get(ALL_FRAMES_AGGREGATES_CACHE_KEY)


def set_cached_frames_aggregates(value, timeout=None):
    return cache.set(ALL_FRAMES_AGGREGATES_CACHE_KEY, value, timeout=timeout)
