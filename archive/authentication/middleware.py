import logging

from django.conf import settings
from django.http import HttpResponseBadRequest
from rest_framework.authentication import TokenAuthentication
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class RemoteUserLogMiddleware(object):
    ''' This Middleware sets request.META['REMOTE_USER'] to the authenticated username (or 'anonymous')

        It can be added to the gunicorn access log with the token: %({remote_user}e)s

        It should be placed after Authentication middleware (and DRFTokenAuthMiddleware) so that
        request.user is populated by the time this runs.
    '''
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            username = request.user.username or 'anonymous'
        except AttributeError:
            username = 'anonymous'

        request.META['REMOTE_USER'] = username

        return self.get_response(request)


class LimitAnonymousAccessMiddleware(object):
    ''' This Middleware blocks unauthenticated GET requests with large limits and offsets
    '''
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If this is an unauthenticated GET request, check the offset and limit and block if theyre too large
        if request.method == 'GET' and not request.user.is_authenticated:
            offset = request.GET.get('offset')
            if offset and offset.isdigit() and int(offset) > settings.MAX_UNAUTHENTICATED_OFFSET:
                return HttpResponseBadRequest("Large offset not allowed for anonymous users.")

            limit = request.GET.get('limit')
            if limit and limit.isdigit() and int(limit) > settings.MAX_UNAUTHENTICATED_LIMIT:
                return HttpResponseBadRequest("Large limit not allowed for anonymous users.")

        return self.get_response(request)


class DRFTokenAuthMiddleware(object):
    ''' This Middleware detects if an API Token is provided and authenticates the request.user with that Token
    
        It should be placed after Authentication middleware, and before middleware that uses the request.user
    '''
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is a Token Auth request based on the Auth header having `Token` in it.
        if request.method == 'GET' and request.headers.get('Authorization', '').startswith('Token'):
            drf_request = Request(request)
            try:
                user_auth = TokenAuthentication().authenticate(drf_request)
                # Set the request.user field if we successfully authenticate with TokenAuthentication
                if user_auth:
                    request.user = user_auth[0]
            except Exception:
                # Mask the token: it's a live credential, so only log a short prefix
                # to allow correlation/debugging without leaking a replayable secret.
                token = request.headers.get('Authorization', '').split(' ', 1)[-1]
                masked_token = f'{token[:6]}...' if token else '(none)'
                logger.warning('DRFTokenAuthMiddleware: Failed to authenticate with token %s', masked_token, exc_info=True)
        return self.get_response(request)
