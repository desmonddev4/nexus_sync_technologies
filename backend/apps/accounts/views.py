from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccountProfile


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            return Response(
                {
                    "username": request.user.get_username(),
                    "role": "superuser",
                    "can_access_operations": True,
                }
            )
        try:
            role = request.user.profile.role
        except AccountProfile.DoesNotExist:
            role = None
        allowed_roles = {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }
        return Response(
            {
                "username": request.user.get_username(),
                "role": role,
                "can_access_operations": role in allowed_roles,
            }
        )