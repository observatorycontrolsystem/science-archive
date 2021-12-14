from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings


class LimitedLimitOffsetPagination(LimitOffsetPagination):
    default_limit = settings.PAGINATION_DEFAULT_LIMIT 
    max_limit = settings.PAGINATION_MAX_LIMIT 
