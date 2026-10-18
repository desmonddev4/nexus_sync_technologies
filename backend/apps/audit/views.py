from datetime import datetime, time, timedelta
import csv

from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event

from .models import AuditLog


def _require_operations_access(user):
    if user.is_superuser:
        return
    try:
        role = user.profile.role
    except AccountProfile.DoesNotExist:
        role = None
    if role not in {
        AccountProfile.Role.EMERGENCY_COORDINATOR,
        AccountProfile.Role.CLINICIAN,
    }:
        raise PermissionDenied("This account cannot access audit logs.")


def _require_export_access(user):
    if user.is_superuser:
        return
    try:
        role = user.profile.role
    except AccountProfile.DoesNotExist:
        role = None
    if role != AccountProfile.Role.EMERGENCY_COORDINATOR:
        raise PermissionDenied("Only emergency coordinators or superusers may export audit logs.")


def _filtered_audit_queryset(request):
    _require_operations_access(request.user)
    queryset = AuditLog.objects.select_related("actor").all()

    actor = request.query_params.get("actor")
    if actor:
        try:
            actor_id = int(actor)
        except ValueError:
            user = get_user_model().objects.filter(username=actor).first()
            if not user:
                raise ValidationError({"actor": _("Actor must be a valid user ID or existing username.")})
            actor_id = user.pk
        queryset = queryset.filter(actor_id=actor_id)

    action = request.query_params.get("action")
    if action:
        queryset = queryset.filter(action__icontains=action)

    resource = request.query_params.get("resource")
    if resource:
        queryset = queryset.filter(resource_type__icontains=resource)

    outcome = request.query_params.get("outcome")
    if outcome:
        allowed_outcomes = {choice for choice, _ in AuditLog.Outcome.choices}
        if outcome not in allowed_outcomes:
            raise ValidationError({"outcome": _("Outcome is not valid.")})
        queryset = queryset.filter(outcome=outcome)

    start_date = request.query_params.get("start_date")
    if start_date:
        parsed = parse_date(start_date)
        if not parsed:
            raise ValidationError({"start_date": _("Use YYYY-MM-DD format.")})
        start_dt = make_aware(datetime.combine(parsed, time.min))
        queryset = queryset.filter(created_at__gte=start_dt)

    end_date = request.query_params.get("end_date")
    if end_date:
        parsed = parse_date(end_date)
        if not parsed:
            raise ValidationError({"end_date": _("Use YYYY-MM-DD format.")})
        end_exclusive = make_aware(datetime.combine(parsed, time.min)) + timedelta(days=1)
        queryset = queryset.filter(created_at__lt=end_exclusive)

    return queryset


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "created_at",
            "actor",
            "actor_username",
            "action",
            "resource_type",
            "resource_id",
            "outcome",
            "http_method",
            "ip_address",
            "request_id",
            "metadata",
        )
        read_only_fields = fields

    def get_actor_username(self, obj):
        return obj.actor.get_username() if obj.actor else None


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="audit_log.list",
            resource_type="audit_log",
            metadata={"result_count": len(response.data)},
        )
        return response

    def get_queryset(self):
        queryset = _filtered_audit_queryset(self.request)

        limit_value = self.request.query_params.get("limit")
        if limit_value is None:
            return queryset[:100]
        try:
            limit = int(limit_value)
        except ValueError:
            raise ValidationError({"limit": _("Limit must be an integer.")})
        if limit < 1:
            raise ValidationError({"limit": _("Limit must be greater than zero.")})
        return queryset[: min(limit, 500)]


class AuditLogExportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        _require_export_access(request.user)
        queryset = _filtered_audit_queryset(request)
        max_rows = max(1, int(getattr(settings, "AUDIT_EXPORT_MAX_ROWS", 2000)))
        rows = list(queryset.order_by("-created_at")[:max_rows])

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_logs_export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "created_at",
                "actor_username",
                "action",
                "resource_type",
                "resource_id",
                "outcome",
                "http_method",
                "ip_address",
                "request_id",
                "metadata",
            ]
        )
        for entry in rows:
            writer.writerow(
                [
                    str(entry.pk),
                    entry.created_at.isoformat(),
                    entry.actor.get_username() if entry.actor else "",
                    entry.action,
                    entry.resource_type,
                    entry.resource_id,
                    entry.outcome,
                    entry.http_method,
                    entry.ip_address or "",
                    entry.request_id,
                    entry.metadata,
                ]
            )

        record_audit_event(
            request=request,
            action="audit_log.export",
            resource_type="audit_log",
            metadata={"result_count": len(rows), "format": "csv"},
        )
        return response
