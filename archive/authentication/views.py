from rest_framework.generics import RetrieveAPIView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from archive.authentication.serializers import UserSerializer


class UserView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        else:
            return None


class ObtainAuthTokenWithHeaders(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            token, created = Token.objects.get_or_create(user=request.user)
            return Response({'token': token.key})
        else:
            return super().post(request, *args, **kwargs)
