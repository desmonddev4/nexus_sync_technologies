from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import Device, DeviceCredential


class DevicePrincipal:
    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, device):
        self.device = device

    def __str__(self):
        return self.device.device_identifier


class DeviceTokenAuthentication(BaseAuthentication):
    keyword = b"device"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid device authorization header.")

        try:
            credentials = parts[1].decode("utf-8")
            device_identifier, secret = credentials.split(":", 1)
        except (UnicodeDecodeError, ValueError) as error:
            raise AuthenticationFailed("Invalid device credentials.") from error

        credential = (
            DeviceCredential.objects.select_related("device")
            .filter(device__device_identifier=device_identifier)
            .first()
        )
        if credential is None or not credential.matches_secret(secret):
            raise AuthenticationFailed("Invalid device credentials.")
        if credential.revoked_at is not None:
            raise AuthenticationFailed("Device credentials have been revoked.")

        device = credential.device
        if device.status != Device.Status.ACTIVE or device.patient_id is None:
            raise AuthenticationFailed("Device is inactive or not assigned to a patient.")
        if device.device_type not in (Device.Type.WEARABLE, Device.Type.SIMULATOR):
            raise AuthenticationFailed("This device type cannot submit monitoring data.")

        credential.last_used_at = timezone.now()
        credential.save(update_fields=("last_used_at", "updated_at"))
        return DevicePrincipal(device), device

    def authenticate_header(self, request):
        return "Device"