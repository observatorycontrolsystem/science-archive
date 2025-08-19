from rest_framework.pagination import LimitOffsetPagination, CursorPagination
from django.conf import settings
from django.db import connections, transaction, OperationalError, InternalError
from django.utils import dateparse

from datetime import timedelta
import sys
import logging
logger = logging.getLogger(__name__)


class CustomCursorPagination(CursorPagination):
    page_size_query_param='limit'
    page_size = settings.PAGINATION_DEFAULT_LIMIT
    max_page_size = settings.PAGINATION_MAX_LIMIT


class LimitedLimitOffsetPagination(LimitOffsetPagination):
    default_limit = settings.PAGINATION_DEFAULT_LIMIT
    max_limit = settings.PAGINATION_MAX_LIMIT

    def __init__(self):
        self.small_query = False
        self.force_count = False
        super().__init__()

    def get_count(self, queryset):
        """
        Combination of ideas from:
         - https://gist.github.com/noviluni/d86adfa24843c7b8ed10c183a9df2afe
         - https://gist.github.com/safar/3bbf96678f3e479b6cb683083d35cb4d
         - https://medium.com/@hakibenita/optimizing-django-admin-paginator-53c4eb6bfca3
        Overrides the count method of QuerySet objects to avoid timeouts.
        - Try to get the real count limiting the queryset execution time to 5000 ms if this is a "small" query.
        - If large query or count takes longer than 5000 ms the database kills the query and raises OperationError. In that case,
        get an estimate instead of actual count when not filtered (this estimate can be stale and hence not fit for
        situations where the count of objects actually matter).
        - If any other exception occured fall back to no count (large number returned).
        """
        self.count_estimated = False
        # Only attempt to get the real count if we have already determined this is a "small" query
        if self.small_query:
            # Limit to 5000 ms if force_count is used, otherwise 1500 ms
            timeout = '5000' if self.force_count else '1500'
            try:
                with transaction.atomic(using='replica'), connections['replica'].cursor() as cursor:
                    cursor.execute(f'SET LOCAL statement_timeout TO {timeout};')
                    return super().get_count(queryset)
            except (OperationalError, InternalError):
                logger.warning(f"Getting the count timed out after {timeout} milliseconds")

        self.count_estimated = True
        if not queryset.query.where:
            logger.warning("Estimating the count using postgres stats table")
            try:
                with transaction.atomic(using='replica'), connections['replica'].cursor() as cursor:
                    # Obtain estimated values (only valid with PostgreSQL)
                    cursor.execute(
                        "SELECT reltuples FROM pg_class WHERE relname = %s",
                        [queryset.query.model._meta.db_table]
                    )
                    estimate = int(cursor.fetchone()[0])
                    return estimate
            except Exception as e:
                logger.warning("Failed to estimate count", exc_info=e)
        else:
            logger.warning("Estimating the count using the postgres query planner")
            try:
                with transaction.atomic(using='replica'), connections['replica'].cursor() as cursor:
                    # Obtain estimated values using the query planner (only valid with PostgreSQL)
                    sql = cursor.mogrify(*queryset.query.sql_with_params()).decode("utf-8")
                    cursor.execute(
                        "SELECT count_estimate(%s);",
                        [sql]
                    )
                    estimate = int(cursor.fetchone()[0])
                    return estimate
            except Exception as e:
                logger.warning("Failed to estimate count", exc_info=e)

        return sys.maxsize

    def paginate_queryset(self, queryset, request, view=None):
        # If certain conditions are met, this is a "small" query and we can attempt a real count
        query_params = dict(request.query_params)
        # If these indexed fields are in the query params, query should be small and bounded so allow full count
        # Also have a fallback 'force_count' param to force it to attempt the full count
        if 'force_count' in query_params and request.user.is_authenticated:
            self.force_count = True
            self.small_query = True
        # /versions/?md5= queries need the accurate count for shipping data in
        elif request.path == '/versions/' and 'md5' in query_params:
            self.force_count = True
            self.small_query = True
        # /thumbnails/ queries with indexed fields can have the full count
        elif request.path == '/thumbnails/' and ('frame_basename' in query_params or 'observation_id' in query_params or 'request_id' in query_params):
            self.small_query = True
        elif request.path == '/frames/':
            # /frames/ queries with indexed fields, or with a small timerange and other common fields.
            if 'request_id' in query_params or 'observation_id' in query_params or 'basename_exact' in query_params:
                self.small_query = True
            elif 'start' in query_params and 'end' in query_params:
                timespan = dateparse.parse_datetime(request.query_params.get('end')) - dateparse.parse_datetime(request.query_params.get('start'))
                # Allow 1 week of querys with no other params
                if timespan <= timedelta(days=7):
                    self.small_query = True
                # Or up to 2 months of querys with some other bounding params
                elif timespan <= timedelta(weeks=9) and any(field in query_params for field in ['proposal_id', 'target_name_exact']):
                    self.small_query = True

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        resp = super().get_paginated_response(data)
        resp.data["count_estimated"] = self.count_estimated

        return resp

    def get_paginated_response_schema(self, schema):
        resp_schema = super().get_paginated_response_schema(schema)

        resp_schema["properties"]["count_estimated"] = {
            "type": "boolean",
        }
        return resp_schema
