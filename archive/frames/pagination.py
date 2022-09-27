from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings
from django.db import connections, transaction, OperationalError, InternalError

import sys
import logging
logger = logging.getLogger(__name__)

class LimitedLimitOffsetPagination(LimitOffsetPagination):
    default_limit = settings.PAGINATION_DEFAULT_LIMIT
    max_limit = settings.PAGINATION_MAX_LIMIT

    """
    Combination of ideas from:
     - https://gist.github.com/noviluni/d86adfa24843c7b8ed10c183a9df2afe
     - https://gist.github.com/safar/3bbf96678f3e479b6cb683083d35cb4d
     - https://medium.com/@hakibenita/optimizing-django-admin-paginator-53c4eb6bfca3
    Overrides the count method of QuerySet objects to avoid timeouts.
    - Try to get the real count limiting the queryset execution time to 5000 ms.
    - If count takes longer than 5000 ms the database kills the query and raises OperationError. In that case,
    get an estimate instead of actual count when not filtered (this estimate can be stale and hence not fit for
    situations where the count of objects actually matter).
    - If any other exception occured fall back to no count (large number returned).
    """
    def get_count(self, queryset):
        try:
            with transaction.atomic(using='replica'), connections['replica'].cursor() as cursor:
                # Limit to 5000 ms
                cursor.execute('SET LOCAL statement_timeout TO 5000;')
                return super().get_count(queryset)
        except (OperationalError, InternalError):
            logger.warning("Getting the count timed out after 5 seconds")
            pass

        if not queryset.query.where:
            try:
                with transaction.atomic(using='replica'), connections['replica'].cursor() as cursor:
                    # Obtain estimated values (only valid with PostgreSQL)
                    cursor.execute(
                        "SELECT reltuples FROM pg_class WHERE relname = %s",
                        [queryset.query.model._meta.db_table]
                    )
                    estimate = int(cursor.fetchone()[0])
                    return estimate
            except Exception:
                # If any other exception occurred fall back to no count
                pass
        return sys.maxsize
