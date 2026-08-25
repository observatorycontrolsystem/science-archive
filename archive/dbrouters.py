from contextvars import ContextVar

# Set per request by ReadRoutingMiddleware - keeps track of if an authenticated user
# was found in the middleware. Used in the Database reader routing.
authenticated_request = ContextVar('authenticated_request', default=False)

# Logging in writes a session and reads it back, along with the user row, on the very next
# request - too soon to rely on replication.
AUTHENTICATION_APPS = frozenset(['sessions', 'auth'])


class ReadRoutingMiddleware:
    """
    Record whether the request is authenticated so that DBClusterRouter can route
    unauthenticated reads to the replica DB

    Database routers aren't given the request, so the decision has to be passed to the router
    out of band. This must run after AuthenticationMiddleware and DRFTokenAuthMiddleware,
    which are what populate request.user.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # request.user is missing if this middleware is ever placed before the auth middleware
        user = getattr(request, 'user', None)
        token = authenticated_request.set(user is not None and user.is_authenticated)
        try:
            return self.get_response(request)
        finally:
            authenticated_request.reset(token)


class DBClusterRouter:
    """
    Database router that splits queries between reader and writer endpoints.
    """
    def db_for_read(self, model, **hints):
        """
        Reads for authenticated requests go to the writer endpoint, and reads for
        unauthenticated ones go to the reader endpoint
        """
        if authenticated_request.get() or model._meta.app_label in AUTHENTICATION_APPS:
            return 'default'

        return 'replica'

    def db_for_write(self, model, **hints):
        """
        Writes go the the writer endpoint.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects for both databases since
        they are replica and writer endpoints pointing at the same data.
        """
        db_list = ('default', 'replica')
        if obj1._state.db in db_list and obj2._state.db in db_list:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        All models should appear in both databases
        """
        return True
