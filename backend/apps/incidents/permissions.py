from rest_framework.permissions import BasePermission

from apps.accounts.models import AccountProfile


class CanAccessIncidents(BasePermission):
    staff_roles = {
        AccountProfile.Role.EMERGENCY_COORDINATOR,
        AccountProfile.Role.CLINICIAN,
    }

    def _profile(self, user):
        try:
            return user.profile
        except AccountProfile.DoesNotExist:
            return None

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        profile = self._profile(user)
        return profile is not None and (
            profile.role in self.staff_roles or profile.role == AccountProfile.Role.PATIENT
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        profile = self._profile(user)
        if profile is None:
            return False
        if view.action in {
            "acknowledge",
            "notifications",
            "events",
            "assign_responder",
            "record_dispatch_request",
            "record_dispatch_confirmation",
            "advance_status",
            "route",
        }:
            return profile.role in self.staff_roles
        return profile.role in self.staff_roles or profile.patient_id == obj.patient_id