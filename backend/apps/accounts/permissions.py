from rest_framework.permissions import BasePermission

from apps.audit.models import AuditLog
from apps.audit.services import record_audit_event

from .models import AccountProfile


class CanManageAccounts(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        try:
            role = user.profile.role
        except AccountProfile.DoesNotExist:
            record_audit_event(
                request=request,
                action="account.manage.denied",
                resource_type="account",
                outcome=AuditLog.Outcome.DENIED,
                metadata={"reason": "missing_profile"},
            )
            return False
        if role != AccountProfile.Role.EMERGENCY_COORDINATOR:
            record_audit_event(
                request=request,
                action="account.manage.denied",
                resource_type="account",
                outcome=AuditLog.Outcome.DENIED,
                metadata={"reason": "role_not_allowed", "role": role},
            )
            return False
        return True
