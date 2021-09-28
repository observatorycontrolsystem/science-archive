from rest_framework.generics import RetrieveAPIView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import throttling, status

from archive.authentication.serializers import UserSerializer
from archive.schema import ScienceArchiveSchema


class UserView(RetrieveAPIView):
    schema = ScienceArchiveSchema(tags=['Users'])
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        else:
            return None


class ObtainAuthTokenWithHeaders(ObtainAuthToken):
    schema = ScienceArchiveSchema(tags=['Authentication'])

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            token, _ = Token.objects.get_or_create(user=request.user)
            return Response({'token': token.key})
        else:
            return super().post(request, *args, **kwargs)

    def get_example_request(self):
        return {'username': 'OCSUser',
                'password': 'myStrongPassword##'}


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
        return Response('ok', status=status.HTTP_200_OK)

    def get_endpoint_name(self):
        return 'healthCheck'
