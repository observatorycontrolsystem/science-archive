from rest_framework.pagination import LimitOffsetPagination
from archive.settings import PAGINATION_DEFAULT_LIMIT


class LimitedLimitOffsetPagination(LimitOffsetPagination):
    default_limit = PAGINATION_DEFAULT_LIMIT 
