from rest_framework.generics import RetrieveAPIView
from archive.authentication.serializers import UserSerializer


class UserView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated():
            return self.request.user
        else:
            return None
