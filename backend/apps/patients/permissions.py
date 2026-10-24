from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import AccountProfile
from .access import has_patient_access


class CanAccessPatientRecords(BasePermission):
    staff_roles = {AccountProfile.Role.EMERGENCY_COORDINATOR, AccountProfile.Role.CLINICIAN}

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        profile = getattr(user, "profile", None)
        if profile is None:
            return False
        if request.method in SAFE_METHODS:
            return profile.role in self.staff_roles | {AccountProfile.Role.PATIENT, AccountProfile.Role.EMERGENCY_CONTACT}
        return profile.role in self.staff_roles or (profile.role == AccountProfile.Role.PATIENT and view.action in {"caretakers", "revoke_caretaker"})

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        profile = getattr(user, "profile", None)
        if profile is None:
            return False
        if profile.role in self.staff_roles:
            return True
        if profile.role == AccountProfile.Role.PATIENT:
            return profile.patient_id == obj.pk and (request.method in SAFE_METHODS or view.action in {"caretakers", "revoke_caretaker"})
        if profile.role == AccountProfile.Role.EMERGENCY_CONTACT and request.method in SAFE_METHODS:
            scope = {"measurements": "health", "devices": "devices", "locations": "location", "caretakers": "patient"}.get(view.action, "patient")
            return has_patient_access(user, obj, scope)
        return False

class CanManagePatientDataRequests(BasePermission):
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
        return profile is not None and profile.role in self.staff_roles | {AccountProfile.Role.PATIENT}

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        profile = self._profile(user)
        if profile is None:
            return False
        if profile.role in self.staff_roles:
            return True
        return profile.role == AccountProfile.Role.PATIENT and profile.patient_id == obj.patient_id
