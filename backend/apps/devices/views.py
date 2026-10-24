from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event

from .models import Device, DeviceCredential
from .permissions import CanManageDevices, IsAuthenticatedDevice
from .serializers import DeviceHeartbeatSerializer, DeviceManagementSerializer


class DeviceHeartbeatView(APIView):
    permission_classes = [IsAuthenticatedDevice]

    def post(self, request):
        serializer = DeviceHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = request.auth
        device.last_seen_at = timezone.now()
        update_fields = ["last_seen_at", "updated_at"]
        for field in ("battery_percent", "firmware_version"):
            if field in serializer.validated_data:
                setattr(device, field, serializer.validated_data[field])
                update_fields.append(field)
        device.save(update_fields=update_fields)

        return Response(
            {
                "device_id": device.device_identifier,
                "status": device.status,
                "battery_percent": device.battery_percent,
                "firmware_version": device.firmware_version,
                "last_seen_at": device.last_seen_at,
            }
        )


class DeviceRegistryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Device.objects.select_related("patient", "credential").all()
    serializer_class = DeviceManagementSerializer
    permission_classes = [CanManageDevices]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                device = serializer.save()
        except IntegrityError as error:
            raise ValidationError({"device_identifier": "A device with this identifier is already registered."}) from error
        record_audit_event(
            request=self.request,
            action="device.registered",
            resource_type="device",
            resource_id=device.pk,
            metadata={"device_type": device.device_type, "patient_linked": bool(device.patient_id)},
        )

    def perform_update(self, serializer):
        device = serializer.save()
        record_audit_event(
            request=self.request,
            action="device.updated",
            resource_type="device",
            resource_id=device.pk,
            metadata={"device_type": device.device_type, "patient_linked": bool(device.patient_id)},
        )

    @action(detail=True, methods=("post",), url_path="issue-credential")
    def issue_credential(self, request, pk=None):
        device = self.get_object()
        if device.status != Device.Status.ACTIVE or device.patient_id is None:
            return Response(
                {"detail": "Activate and assign the device to a patient before issuing credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if device.device_type not in {Device.Type.WEARABLE, Device.Type.SIMULATOR}:
            return Response(
                {"detail": "Credentials can only be issued to wearable or simulator devices."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = DeviceCredential.issue(device)
        record_audit_event(
            request=request,
            action="device.credential_issued",
            resource_type="device",
            resource_id=device.pk,
            metadata={"rotation": True},
        )
        return Response(
            {
                "device": self.get_serializer(device).data,
                "secret": secret,
                "warning": "Copy this secret now. It will not be shown again.",
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=("post",), url_path="revoke-credential")
    def revoke_credential(self, request, pk=None):
        device = self.get_object()
        credential = DeviceCredential.objects.filter(device=device).first()
        if credential is None or credential.revoked_at is not None:
            return Response({"detail": "No active credential exists for this device."}, status=status.HTTP_400_BAD_REQUEST)
        credential.revoked_at = timezone.now()
        credential.save(update_fields=("revoked_at", "updated_at"))
        device.credential = credential
        record_audit_event(
            request=request,
            action="device.credential_revoked",
            resource_type="device",
            resource_id=device.pk,
        )
        return Response(self.get_serializer(device).data)