from django.shortcuts import get_object_or_404
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event
from apps.devices.models import Device
from .models import Measurement, MonitoringRule
from .serializers import (
    MonitoringRuleEvaluationSerializer,
    MonitoringRuleReviewSerializer,
    MonitoringRuleSerializer,
    MeasurementIngestSerializer,
    MeasurementQualityDecisionSerializer,
    MeasurementQualityReviewSerializer,
    MeasurementSerializer,
    PatientLocationIngestSerializer,
    PatientLocationSerializer,
)
from .services import evaluate_measurement_for_rules, ingest_measurement, ingest_patient_location


def _get_role(user):
    if user.is_superuser:
        return "superuser"
    try:
        return user.profile.role
    except AccountProfile.DoesNotExist:
        return None


def _require_operations_access(user):
    role = _get_role(user)
    if role in {
        "superuser",
        AccountProfile.Role.EMERGENCY_COORDINATOR,
        AccountProfile.Role.CLINICIAN,
    }:
        return
    raise PermissionDenied("This account cannot access monitoring rule management.")


def _require_clinician_review_access(user):
    role = _get_role(user)
    if role in {"superuser", AccountProfile.Role.CLINICIAN}:
        return
    raise PermissionDenied("Only a clinician or superuser may manage rule review and enablement.")


def _require_measurement_review_access(user):
    role = _get_role(user)
    if role in {"superuser", AccountProfile.Role.CLINICIAN}:
        return
    raise PermissionDenied("Only a clinician or superuser may review measurement quality.")


def _parse_limit(raw_value, default=20):
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValidationError({"limit": _("Limit must be an integer.")})
    if value < 1:
        raise ValidationError({"limit": _("Limit must be greater than zero.")})
    return min(value, 200)


class MeasurementIngestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MeasurementIngestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        measurement, created = ingest_measurement(
            data=serializer.validated_data,
            actor=None if isinstance(request.auth, Device) else request.user,
        )
        record_audit_event(
            request=request,
            action="measurement.ingested" if created else "measurement.retry",
            resource_type="measurement",
            resource_id=measurement.pk,
            metadata={
                "device_identifier": request.auth.device_identifier
                if isinstance(request.auth, Device)
                else "",
            },
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(MeasurementSerializer(measurement).data, status=response_status)


class MeasurementQualityQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_measurement_review_access(request.user)
        limit = _parse_limit(request.query_params.get("limit"), default=50)
        queryset = Measurement.objects.select_related("patient", "device", "quality_reviewed_by")
        quality = request.query_params.get("quality", Measurement.Quality.UNREVIEWED)
        if quality not in Measurement.Quality.values:
            raise ValidationError({"quality": "Choose a valid measurement quality."})
        queryset = queryset.filter(quality=quality)
        measurement_type = request.query_params.get("measurement_type")
        if measurement_type:
            if measurement_type not in Measurement.Type.values:
                raise ValidationError({"measurement_type": "Choose a valid measurement type."})
            queryset = queryset.filter(measurement_type=measurement_type)
        patient_id = request.query_params.get("patient")
        if patient_id:
            try:
                UUID(patient_id)
            except (TypeError, ValueError) as error:
                raise ValidationError({"patient": "Patient must be a valid UUID."}) from error
            queryset = queryset.filter(patient_id=patient_id)
        measurements = list(queryset.order_by("measured_at", "id")[:limit])
        record_audit_event(
            request=request,
            action="measurement.quality_queue.read",
            resource_type="measurement",
            metadata={"result_count": len(measurements), "quality": quality},
        )
        return Response(MeasurementQualityReviewSerializer(measurements, many=True).data)


class MeasurementQualityReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, measurement_id):
        _require_measurement_review_access(request.user)
        measurement = get_object_or_404(
            Measurement.objects.select_for_update().select_related("patient"),
            pk=measurement_id,
        )
        if measurement.quality != Measurement.Quality.UNREVIEWED:
            raise ValidationError({"quality": "This measurement has already been reviewed."})
        serializer = MeasurementQualityDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        measurement.quality = serializer.validated_data["quality"]
        measurement.quality_reviewed_by = request.user
        measurement.quality_reviewed_at = timezone.now()
        measurement.save(update_fields=("quality", "quality_reviewed_by", "quality_reviewed_at", "updated_at"))
        record_audit_event(
            request=request,
            action="measurement.quality_reviewed",
            resource_type="measurement",
            resource_id=measurement.pk,
            metadata={"quality": measurement.quality},
        )
        if measurement.quality == Measurement.Quality.ACCEPTABLE:
            evaluate_measurement_for_rules(measurement)
        measurement = Measurement.objects.select_related("patient", "device", "quality_reviewed_by").get(pk=measurement.pk)
        return Response(MeasurementQualityReviewSerializer(measurement).data)


class PatientLocationIngestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PatientLocationIngestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        location, created = ingest_patient_location(
            data=serializer.validated_data,
            actor=None if isinstance(request.auth, Device) else request.user,
        )
        record_audit_event(
            request=request,
            action="patient_location.ingested" if created else "patient_location.retry",
            resource_type="patient_location",
            resource_id=location.pk,
            metadata={
                "device_identifier": request.auth.device_identifier
                if isinstance(request.auth, Device)
                else "",
            },
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(PatientLocationSerializer(location).data, status=response_status)


class MonitoringRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = MonitoringRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require_operations_access(self.request.user)
        queryset = MonitoringRule.objects.all().order_by("name", "version")
        measurement_type = self.request.query_params.get("measurement_type")
        if measurement_type:
            queryset = queryset.filter(measurement_type=measurement_type)
        enabled = self.request.query_params.get("is_enabled")
        if enabled in {"true", "false"}:
            queryset = queryset.filter(is_enabled=(enabled == "true"))
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="monitoring_rule.list",
            resource_type="monitoring_rule",
            metadata={"result_count": len(response.data)},
        )
        return response

    def perform_create(self, serializer):
        _require_clinician_review_access(self.request.user)
        rule = serializer.save(is_enabled=False, reviewed_by=None, reviewed_at=None)
        record_audit_event(
            request=self.request,
            action="monitoring_rule.created",
            resource_type="monitoring_rule",
            resource_id=rule.pk,
        )


class MonitoringRuleDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MonitoringRuleSerializer
    permission_classes = [IsAuthenticated]
    queryset = MonitoringRule.objects.all()

    def get_object(self):
        _require_operations_access(self.request.user)
        rule = super().get_object()
        record_audit_event(
            request=self.request,
            action="monitoring_rule.read" if self.request.method == "GET" else "monitoring_rule.update.accessed",
            resource_type="monitoring_rule",
            resource_id=rule.pk,
        )
        return rule

    def perform_update(self, serializer):
        _require_clinician_review_access(self.request.user)
        rule = serializer.save()
        record_audit_event(
            request=self.request,
            action="monitoring_rule.updated",
            resource_type="monitoring_rule",
            resource_id=rule.pk,
        )


class MonitoringRuleReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rule_id):
        _require_clinician_review_access(request.user)
        rule = get_object_or_404(MonitoringRule, pk=rule_id)
        serializer = MonitoringRuleReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rule.is_enabled = serializer.validated_data["is_enabled"]
        if rule.is_enabled:
            rule.reviewed_by = request.user
            rule.reviewed_at = timezone.now()
            action = "monitoring_rule.enabled"
        else:
            action = "monitoring_rule.disabled"
        rule.save(update_fields=("is_enabled", "reviewed_by", "reviewed_at", "updated_at"))

        record_audit_event(
            request=request,
            action=action,
            resource_type="monitoring_rule",
            resource_id=rule.pk,
        )
        return Response(MonitoringRuleSerializer(rule).data)


class MonitoringRuleEvaluationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rule_id):
        _require_operations_access(request.user)
        rule = get_object_or_404(MonitoringRule, pk=rule_id)
        limit = _parse_limit(request.query_params.get("limit"))
        evaluations = rule.evaluations.order_by("-created_at")[:limit]
        record_audit_event(
            request=request,
            action="monitoring_rule.evaluations.read",
            resource_type="monitoring_rule",
            resource_id=rule.pk,
            metadata={"result_count": len(evaluations)},
        )
        return Response(MonitoringRuleEvaluationSerializer(evaluations, many=True).data)