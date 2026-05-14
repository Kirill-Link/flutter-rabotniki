from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, AuthUser
from rest_framework_simplejwt.tokens import Token
from rest_framework import serializers

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user: AuthUser) -> Token:
        token = super().get_token(user)

        token['username'] = user.username
        token['full_name'] = f"{user.last_name} {user.first_name}"

        return token


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class LogOutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)