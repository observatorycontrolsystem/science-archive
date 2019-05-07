import boto3
from functools import lru_cache


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


def build_nginx_zip_text(frames, filename):
    nginx_line = '- {0} /s3/{1} {2}/{3}{4}\n'
    return_line = ''
    for frame in frames:
        return_line += nginx_line.format(
            frame.size, frame.s3_key, filename, frame.basename, frame.version_set.first().extension
        )
    return return_line
