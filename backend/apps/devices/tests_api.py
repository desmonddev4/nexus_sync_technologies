from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
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


class DeviceRegistryApiTests(APITestCase):
    def setUp(self):
        self.patient = Patient.objects.create(full_name="Provisioned Device Patient")
        user_model = get_user_model()
        self.coordinator = user_model.objects.create_user(username="device-manager")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.clinician = user_model.objects.create_user(username="device-clinician")
        AccountProfile.objects.create(user=self.clinician, role=AccountProfile.Role.CLINICIAN)
        self.client.force_authenticate(self.coordinator)

    def test_coordinator_can_register_and_assign_device(self):
        response = self.client.post(
            "/api/v1/device-registry/",
            {
                "device_identifier": "NS-REGISTRY-001",
                "device_type": Device.Type.SIMULATOR,
                "patient": str(self.patient.pk),
                "status": Device.Status.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        device = Device.objects.get(device_identifier="NS-REGISTRY-001")
        self.assertEqual(device.patient, self.patient)
        self.assertEqual(device.status, Device.Status.ACTIVE)
        self.assertTrue(AuditLog.objects.filter(action="device.registered", resource_id=str(device.pk)).exists())

    def test_non_coordinator_cannot_manage_devices(self):
        self.client.force_authenticate(self.clinician)

        response = self.client.post(
            "/api/v1/device-registry/",
            {"device_identifier": "NS-FORBIDDEN-001", "device_type": Device.Type.SIMULATOR},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Device.objects.filter(device_identifier="NS-FORBIDDEN-001").exists())

    def test_credential_is_one_time_rotatable_and_revocable(self):
        device = Device.objects.create(
            device_identifier="NS-REGISTRY-002",
            device_type=Device.Type.SIMULATOR,
            patient=self.patient,
            status=Device.Status.ACTIVE,
        )
        url = f"/api/v1/device-registry/{device.pk}/"

        first = self.client.post(f"{url}issue-credential/")
        first_secret = first.json()["secret"]
        credential = DeviceCredential.objects.get(device=device)
        self.assertEqual(first.status_code, 201)
        self.assertNotIn(first_secret, credential.secret_digest)
        self.assertEqual(first.json()["device"]["credential_revoked"], False)
        self.assertNotIn("secret", first.json()["device"])

        second = self.client.post(f"{url}issue-credential/")
        second_secret = second.json()["secret"]
        credential.refresh_from_db()
        self.assertNotEqual(first_secret, second_secret)
        self.assertTrue(credential.matches_secret(second_secret))
        self.assertFalse(credential.matches_secret(first_secret))
        credential_audit = AuditLog.objects.filter(action="device.credential_issued").first()
        self.assertNotIn(first_secret, str(credential_audit.metadata))
        self.assertNotIn(second_secret, str(credential_audit.metadata))

        revoked = self.client.post(f"{url}revoke-credential/")
        credential.refresh_from_db()
        self.assertEqual(revoked.status_code, 200)
        self.assertIsNotNone(credential.revoked_at)
        self.assertTrue(revoked.json()["credential_revoked"])

    def test_credential_issue_requires_active_patient_assigned_supported_device(self):
        device = Device.objects.create(
            device_identifier="NS-REGISTRY-003",
            device_type=Device.Type.OTHER,
            patient=None,
            status=Device.Status.REGISTERED,
        )

        response = self.client.post(f"/api/v1/device-registry/{device.pk}/issue-credential/")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceCredential.objects.filter(device=device).exists())