from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.devices.models import Device, DeviceCredential
from apps.patients.models import Patient


class DeviceModelTests(TestCase):
    def test_device_identity_is_unique(self):
        Device.objects.create(device_identifier="NS-DEVICE-001", device_type=Device.Type.SIMULATOR)

        with self.assertRaises(IntegrityError):
            Device.objects.create(
                device_identifier="NS-DEVICE-001",
                device_type=Device.Type.SIMULATOR,
            )

    def test_device_can_be_associated_with_a_patient(self):
        patient = Patient.objects.create(full_name="Test Patient")
        device = Device.objects.create(
            device_identifier="NS-DEVICE-002",
            device_type=Device.Type.WEARABLE,
            patient=patient,
        )

        self.assertEqual(device.patient, patient)
        self.assertEqual(device.status, Device.Status.REGISTERED)

    def test_battery_percentage_is_limited_to_one_hundred(self):
        device = Device(
            device_identifier="NS-DEVICE-003",
            device_type=Device.Type.SIMULATOR,
            battery_percent=101,
        )

        with self.assertRaises(ValidationError):
            device.full_clean()

    def test_issued_secret_is_not_stored_in_plaintext(self):
        patient = Patient.objects.create(full_name="Credential Patient")
        device = Device.objects.create(
            device_identifier="NS-CREDENTIAL-001",
            device_type=Device.Type.WEARABLE,
            patient=patient,
        )

        secret = DeviceCredential.issue(device)
        credential = DeviceCredential.objects.get(device=device)

        self.assertNotEqual(credential.secret_digest, secret)
        self.assertTrue(credential.matches_secret(secret))
        self.assertFalse(credential.matches_secret("incorrect-secret"))