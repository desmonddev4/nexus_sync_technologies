from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAuthenticatedDevice
from .serializers import DeviceHeartbeatSerializer


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