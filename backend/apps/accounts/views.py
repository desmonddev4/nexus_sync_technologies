from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event

from .models import AccountProfile
from .permissions import CanManageAccounts
from .serializers import AccountAdminSerializer


class AuditedObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        username = str(request.data.get("username", ""))[:150]
        if not serializer.is_valid():
            record_audit_event(
                request=request,
                action="auth.token.failed",
                resource_type="auth",
                outcome="failure",
                metadata={"username": username},
            )
            raise ValidationError(serializer.errors)

        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        try:
            role = user.profile.role
        except AccountProfile.DoesNotExist:
            role = ""

        record_audit_event(
            request=request,
            action="auth.token.issued",
            resource_type="auth",
            resource_id=user.pk,
            metadata={"username": user.get_username(), "role": role},
            actor=user,
        )
        return Response({"token": token.key}, status=status.HTTP_200_OK)


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


class AccountListCreateView(generics.ListCreateAPIView):
    serializer_class = AccountAdminSerializer
    permission_classes = [CanManageAccounts]

    def get_queryset(self):
        queryset = get_user_model().objects.select_related("profile", "profile__patient").order_by("username")
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(profile__role=role)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(username__icontains=search)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="account.list",
            resource_type="account",
            metadata={"result_count": len(response.data)},
        )
        return response

    def perform_create(self, serializer):
        user = serializer.save()
        role = getattr(getattr(user, "profile", None), "role", "")
        record_audit_event(
            request=self.request,
            action="account.created",
            resource_type="account",
            resource_id=user.pk,
            metadata={"username": user.get_username(), "role": role},
        )


class AccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AccountAdminSerializer
    permission_classes = [CanManageAccounts]
    queryset = get_user_model().objects.select_related("profile", "profile__patient")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="account.read",
            resource_type="account",
            resource_id=kwargs.get("pk", ""),
        )
        return response

    def perform_update(self, serializer):
        previous_role = getattr(getattr(serializer.instance, "profile", None), "role", "")
        user = serializer.save()
        role = getattr(getattr(user, "profile", None), "role", "")
        record_audit_event(
            request=self.request,
            action="account.updated",
            resource_type="account",
            resource_id=user.pk,
            metadata={
                "username": user.get_username(),
                "previous_role": previous_role,
                "new_role": role,
                "is_active": user.is_active,
            },
        )
class RevokeAuthTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.auth
        if isinstance(token, Token):
            token.delete()
        record_audit_event(
            request=request,
            action="auth.token.revoked",
            resource_type="auth",
            resource_id=request.user.pk,
            actor=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
