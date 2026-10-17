from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.devices.models import Device
from .serializers import (
    MeasurementIngestSerializer,
    MeasurementSerializer,
    PatientLocationIngestSerializer,
    PatientLocationSerializer,
)
from .services import ingest_measurement, ingest_patient_location


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