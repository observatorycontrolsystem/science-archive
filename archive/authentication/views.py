from django.utils.module_loading import import_string
from django.conf import settings
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import throttling, status

from archive.authentication.serializers import UserSerializer, RevokeTokenResponseSerializer
from archive.schema import ScienceArchiveSchema
from archive.doc_examples import EXAMPLE_REQUESTS, EXAMPLE_RESPONSES


class UserView(RetrieveAPIView):
    schema = ScienceArchiveSchema(tags=['Users'])
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        else:
            return None


class ObtainAuthTokenWithHeaders(ObtainAuthToken):
    """
    Obtain the auth token associated with the given user account
    """
    schema = ScienceArchiveSchema(tags=['Authentication'])

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            token, _ = Token.objects.get_or_create(user=request.user)
            return Response({'token': token.key})
        else:
            return super().post(request, *args, **kwargs)

    def get_example_request(self):
        return EXAMPLE_REQUESTS['authentication']['auth_token']

    def get_endpoint_name(self):
        return 'getAuthToken'


class RevokeApiTokenApiView(APIView):
    """View to revoke an API token. 
    Note that the API token is referenced by the name auth_token.
    """
    permission_classes = [IsAuthenticated]
    schema = ScienceArchiveSchema(tags=['Authentication'], empty_request=True)
    serializer_class = RevokeTokenResponseSerializer

    def post(self, request):
        """A simple POST request (empty request body) with user authentication information in the HTTP header will revoke a user's API Token."""
        request.user.auth_token.delete()
        Token.objects.create(user=request.user)
        serializer = self.get_response_serializer({'message': 'API token revoked.'})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_response_serializer(self, *args, **kwargs):
        return RevokeTokenResponseSerializer(*args, **kwargs)

    def get_endpoint_name(self):
        return 'revokeApiToken'


class NoThrottle(throttling.BaseThrottle):
    def allow_request(self, request, view):
        return True


class HealthCheckView(APIView):
    """
    Endpoint to check the health of the Science Archive service
    """
    schema = ScienceArchiveSchema(tags=['Health'])
    throttle_classes = (NoThrottle,)

    def get(self, request, format=None):
        return Response('ok')

    def get_example_response(self):
        return Response(EXAMPLE_RESPONSES['authentication']['health'], status=status.HTTP_200_OK)

    def get_endpoint_name(self):
        return 'healthCheck'
