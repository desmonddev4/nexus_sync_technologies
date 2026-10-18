from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event

from .models import EscalationPolicy
from .serializers import EscalationPolicySerializer


def _can_read_policy(user):
    if user.is_superuser:
        return True
    try:
        role = user.profile.role
    except AccountProfile.DoesNotExist:
        return False
    return role in {
        AccountProfile.Role.EMERGENCY_COORDINATOR,
        AccountProfile.Role.CLINICIAN,
    }


def _can_write_policy(user):
    if user.is_superuser:
        return True
    try:
        role = user.profile.role
    except AccountProfile.DoesNotExist:
        return False
    return role == AccountProfile.Role.EMERGENCY_COORDINATOR


class EscalationPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def get_policy(self):
        policy, _ = EscalationPolicy.objects.get_or_create(singleton_key="default")
        return policy

    def get(self, request):
        if not _can_read_policy(request.user):
            raise PermissionDenied("This account cannot access escalation settings.")
        policy = self.get_policy()
        record_audit_event(
            request=request,
            action="escalation_policy.read",
            resource_type="escalation_policy",
            resource_id=policy.pk,
        )
        return Response(EscalationPolicySerializer(policy).data)

    def patch(self, request):
        if not _can_write_policy(request.user):
            raise PermissionDenied("Only emergency coordinators or superusers can update escalation settings.")
        policy = self.get_policy()
        serializer = EscalationPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save(updated_by=request.user)
        record_audit_event(
            request=request,
            action="escalation_policy.updated",
            resource_type="escalation_policy",
            resource_id=updated.pk,
        )
        return Response(EscalationPolicySerializer(updated).data)
