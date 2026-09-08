from rest_framework.exceptions import APIException


class FunpackError(APIException):
    status_code = 500
    default_detail = 'There was a problem downloading your files. Please try again later or select fewer files.'
    default_code = 'download error'


class ExactCountUnavailable(APIException):
    status_code = 503
    default_detail = 'The database was unable to count the results for this query. Please try again later.'
    default_code = 'count unavailable'
