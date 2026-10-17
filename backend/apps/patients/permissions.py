from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import AccountProfile


class CanAccessPatientRecords(BasePermission):
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
        if profile is None:
            return False
        return profile.role in self.staff_roles or profile.role == AccountProfile.Role.PATIENT

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        profile = self._profile(user)
        if profile is None:
            return False
        if profile.role in self.staff_roles:
            return True
        return (
            profile.role == AccountProfile.Role.PATIENT
            and request.method in SAFE_METHODS
            and profile.patient_id == obj.pk
        )