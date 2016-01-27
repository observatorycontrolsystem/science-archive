import boto3
from functools import lru_cache


@lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client('s3')


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


def build_nginx_zip_text(frames):
    nginx_line = '- {0} /s3/{1} /images/{2}{3}\n'
    return_line = ''
    for frame in frames:
        version = frame.version_set.last()
        return_line += nginx_line.format(
            version.size, version.frame.s3_key, version.frame.basename, version.extension
        )
    return return_line
