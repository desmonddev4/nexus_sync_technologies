from rest_framework.permissions import BasePermission

from apps.accounts.models import AccountProfile


class IsEmergencyOperationsStaff(BasePermission):
    allowed_roles = {
        AccountProfile.Role.EMERGENCY_COORDINATOR,
        AccountProfile.Role.CLINICIAN,
    }

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            return False
        return profile.role in self.allowed_roles


class CanManageEmergencyDirectory(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            return False
        return profile.role == AccountProfile.Role.EMERGENCY_COORDINATOR