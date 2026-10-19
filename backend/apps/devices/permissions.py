from rest_framework.permissions import BasePermission

from apps.accounts.models import AccountProfile

from .models import Device


class IsAuthenticatedDevice(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Device) and request.user.is_authenticated


class CanManageDevices(BasePermission):
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