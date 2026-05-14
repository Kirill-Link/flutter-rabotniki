from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import ChangePasswordSerializer, LogOutSerializer

@extend_schema(
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password successfully changed'),
        400: OpenApiResponse(description='Old password and new password are required/ Old password is incorrect/ New password is the same as old password'),
        401: OpenApiResponse(description='Unauthorized')
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not old_password or not new_password:
        return Response({"error": "Old password and new password are required"}, status=status.HTTP_400_BAD_REQUEST)

    if not user.check_password(old_password):
        return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

    if user.check_password(new_password):
        return Response({"error": "New password is the same as old password"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)

@extend_schema(
    request=LogOutSerializer,
    responses={
        205: OpenApiResponse(description='Logout successfully'),
        400: OpenApiResponse(description='Invalid token / already blacklisted / no refresh in body')
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)

        token.blacklist()

        return Response({"message": "Logout successfully"}, status=status.HTTP_205_RESET_CONTENT)
    except KeyError:
        return Response({"message": "No refresh token in body"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"message": "Error occurred. Invalid token or already blacklisted"}, status=status.HTTP_400_BAD_REQUEST)

