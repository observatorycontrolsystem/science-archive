import boto3
from functools import lru_cache
from django.conf import settings
from datetime import timedelta


@lru_cache(maxsize=1)
def get_s3_client():
    config = boto3.session.Config(region_name='us-west-2', signature_version='s3v4')
    return boto3.client('s3', config=config)


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


def build_nginx_zip_text(frames, directory):
    client = get_s3_client()
    ret = []

    for frame in frames:
        # Parameters for AWS S3 URL signing request
        version = frame.version_set.first()
        bucket, s3_key = version.get_bucket_and_s3_key()
        params = {
            'Key': s3_key,
            'Bucket': bucket,
        }
        # Generate a presigned AWS S3 V4 URL which expires in 86400 seconds (1 day)
        url = client.generate_presigned_url('get_object', Params=params, ExpiresIn=86400)
        # The NGINX mod_zip module requires that the files which are used to build the
        # ZIP file must be loaded from an internal NGINX location. Replace the leading
        # portion of the generated URL with an internal NGINX location which proxies all
        # traffic to AWS S3.
        location = url.replace('https://s3.us-west-2.amazonaws.com', '/s3')
        # The NGINX mod_zip module builds ZIP files using a manifest. Build the manifest
        # line for this frame.
        line = '- {size} {location} {directory}/{basename}{extension}\n'.format(
            size=version.size,
            location=location,
            directory=directory,
            basename=frame.basename,
            extension=version.extension,
        )
        # Add to returned lines
        ret.append(line)

    # Concatenate all lines together into a single string
    return ''.join(ret)
