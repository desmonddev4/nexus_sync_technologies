from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event
from apps.devices.models import Device
from apps.devices.serializers import DeviceHealthSerializer
from apps.monitoring.models import Measurement, PatientLocation
from apps.monitoring.serializers import MeasurementSerializer, PatientLocationSerializer

from .models import Patient
from .models import PatientDataRequest
from .permissions import CanAccessPatientRecords, CanManagePatientDataRequests
from .serializers import PatientDataRequestSerializer, PatientSerializer
from .services import (
    approve_patient_data_request,
    create_patient_data_request,
    fulfill_patient_data_request,
    reject_patient_data_request,
)


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


class PatientViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PatientSerializer
    permission_classes = [CanAccessPatientRecords]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Patient.objects.all()

        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            return Patient.objects.none()

        if profile.role in {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }:
            return Patient.objects.all()
        if profile.role == AccountProfile.Role.PATIENT and profile.patient_id:
            return Patient.objects.filter(pk=profile.patient_id)
        return Patient.objects.none()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="patient.list",
            resource_type="patient",
            metadata={"result_count": len(response.data)},
        )
        return response

    def get_object(self):
        try:
            patient = super().get_object()
        except (Http404, DjangoPermissionDenied, DRFPermissionDenied):
            record_audit_event(
                request=self.request,
                action="patient.access_denied",
                resource_type="patient",
                resource_id=self.kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""),
                outcome="denied",
            )
            raise
        record_audit_event(
            request=self.request,
            action="patient.read" if self.action == "retrieve" else f"patient.{self.action}.accessed",
            resource_type="patient",
            resource_id=patient.pk,
        )
        return patient

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        patient = serializer.save()
        record_audit_event(
            request=self.request,
            action="patient.created",
            resource_type="patient",
            resource_id=patient.pk,
        )

    def perform_update(self, serializer):
        patient = serializer.save()
        record_audit_event(
            request=self.request,
            action="patient.updated",
            resource_type="patient",
            resource_id=patient.pk,
        )

    @action(detail=True, methods=["get"], url_path="measurements")
    def measurements(self, request, pk=None):
        patient = self.get_object()
        limit = _parse_limit(request.query_params.get("limit"))
        queryset = Measurement.objects.filter(patient=patient).order_by("-measured_at")[:limit]
        record_audit_event(
            request=request,
            action="patient.measurements.read",
            resource_type="patient",
            resource_id=patient.pk,
            metadata={"result_count": len(queryset)},
        )
        return Response(MeasurementSerializer(queryset, many=True).data)

    @action(detail=True, methods=["get"], url_path="locations")
    def locations(self, request, pk=None):
        patient = self.get_object()
        limit = _parse_limit(request.query_params.get("limit"))
        queryset = PatientLocation.objects.filter(patient=patient).order_by("-recorded_at")[:limit]
        record_audit_event(
            request=request,
            action="patient.locations.read",
            resource_type="patient",
            resource_id=patient.pk,
            metadata={"result_count": len(queryset)},
        )
        return Response(PatientLocationSerializer(queryset, many=True).data)

    @action(detail=True, methods=["get"], url_path="devices")
    def devices(self, request, pk=None):
        patient = self.get_object()
        queryset = Device.objects.filter(patient=patient).order_by("device_identifier")
        record_audit_event(
            request=request,
            action="patient.devices.read",
            resource_type="patient",
            resource_id=patient.pk,
            metadata={"result_count": queryset.count()},
        )
        return Response(DeviceHealthSerializer(queryset, many=True).data)


class PatientDataRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PatientDataRequestSerializer
    permission_classes = [CanManagePatientDataRequests]

    def get_queryset(self):
        user = self.request.user
        queryset = PatientDataRequest.objects.select_related(
            "patient",
            "requested_by",
            "reviewed_by",
            "fulfilled_by",
        )
        if user.is_superuser:
            return queryset
        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            return queryset.none()
        if profile.role in {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }:
            return queryset
        if profile.role == AccountProfile.Role.PATIENT and profile.patient_id:
            return queryset.filter(patient_id=profile.patient_id)
        return queryset.none()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="patient_data_request.list",
            resource_type="patient_data_request",
            metadata={"result_count": len(response.data)},
        )
        return response

    def _require_staff(self, request):
        if request.user.is_superuser:
            return
        profile = getattr(request.user, "profile", None)
        if profile is None or profile.role not in {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }:
            raise DRFPermissionDenied("Only staff can review or fulfill patient data requests.")

    def retrieve(self, request, *args, **kwargs):
        request_obj = self.get_object()
        serializer = self.get_serializer(request_obj)
        record_audit_event(
            request=request,
            action="patient_data_request.read",
            resource_type="patient_data_request",
            resource_id=request_obj.pk,
        )
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        profile = getattr(request.user, "profile", None)
        if profile and profile.role == AccountProfile.Role.PATIENT and profile.patient_id != patient.pk:
            raise ValidationError({"patient": "Patients may only request their own data."})
        if profile and profile.role == AccountProfile.Role.PATIENT and not patient:
            raise ValidationError({"patient": "Patient is required."})

        data_request = create_patient_data_request(
            patient=patient,
            requested_by=request.user,
            request_type=serializer.validated_data["request_type"],
            reason=serializer.validated_data.get("reason", ""),
        )
        record_audit_event(
            request=request,
            action="patient_data_request.created",
            resource_type="patient_data_request",
            resource_id=data_request.pk,
            metadata={"request_type": data_request.request_type, "patient": str(patient.pk)},
        )
        output = self.get_serializer(data_request)
        return Response(output.data, status=201)

    @action(detail=True, methods=("post",), url_path="approve")
    def approve(self, request, pk=None):
        self._require_staff(request)
        data_request = self.get_object()
        try:
            approved = approve_patient_data_request(
                data_request=data_request,
                reviewer=request.user,
                notes=request.data.get("notes", ""),
            )
        except ValueError as error:
            raise ValidationError({"status": str(error)}) from error
        record_audit_event(
            request=request,
            action="patient_data_request.approved",
            resource_type="patient_data_request",
            resource_id=approved.pk,
            metadata={"request_type": approved.request_type},
        )
        return Response(self.get_serializer(approved).data)

    @action(detail=True, methods=("post",), url_path="reject")
    def reject(self, request, pk=None):
        self._require_staff(request)
        data_request = self.get_object()
        try:
            rejected = reject_patient_data_request(
                data_request=data_request,
                reviewer=request.user,
                notes=request.data.get("notes", ""),
            )
        except ValueError as error:
            raise ValidationError({"status": str(error)}) from error
        record_audit_event(
            request=request,
            action="patient_data_request.rejected",
            resource_type="patient_data_request",
            resource_id=rejected.pk,
        )
        return Response(self.get_serializer(rejected).data)

    @action(detail=True, methods=("post",), url_path="fulfill")
    def fulfill(self, request, pk=None):
        self._require_staff(request)
        data_request = self.get_object()
        try:
            fulfilled = fulfill_patient_data_request(
                data_request=data_request,
                fulfiller=request.user,
            )
        except ValueError as error:
            raise ValidationError({"status": str(error)}) from error
        record_audit_event(
            request=request,
            action="patient_data_request.fulfilled",
            resource_type="patient_data_request",
            resource_id=fulfilled.pk,
            metadata={"request_type": fulfilled.request_type},
        )
        return Response(self.get_serializer(fulfilled).data)