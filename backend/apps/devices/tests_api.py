from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.devices.models import Device, DeviceCredential
from apps.patients.models import Patient


class DeviceHeartbeatApiTests(APITestCase):
    def setUp(self):
        patient = Patient.objects.create(full_name="Heartbeat Patient")
        self.device = Device.objects.create(
            device_identifier="NS-HEARTBEAT-001",
            device_type=Device.Type.WEARABLE,
            patient=patient,
            status=Device.Status.ACTIVE,
        )
        secret = DeviceCredential.issue(self.device)
        self.device_client = APIClient()
        self.device_client.credentials(
            HTTP_AUTHORIZATION=f"Device {self.device.device_identifier}:{secret}"
        )

    def test_device_heartbeat_updates_status_using_server_time(self):
        response = self.device_client.post(
            "/api/v1/devices/heartbeat/",
            {"battery_percent": 86, "firmware_version": "pilot-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.battery_percent, 86)
        self.assertEqual(self.device.firmware_version, "pilot-1")
        self.assertIsNotNone(self.device.last_seen_at)

    def test_user_token_cannot_send_device_heartbeat(self):
        user = get_user_model().objects.create_user(username="not-a-device")
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/devices/heartbeat/",
            {"battery_percent": 50},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_battery_is_rejected_without_updating_device(self):
        response = self.device_client.post(
            "/api/v1/devices/heartbeat/",
            {"battery_percent": 101},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.battery_percent)
        self.assertIsNone(self.device.last_seen_at)