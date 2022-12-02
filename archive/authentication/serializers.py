from rest_framework import serializers
from django.contrib.auth.models import User
from archive.authentication.models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('proposals', )


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('username', 'profile', 'is_staff')

class RevokeTokenResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default='API token revoked.')
