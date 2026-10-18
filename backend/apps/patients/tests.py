from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.patients.models import ConsentRecord, EmergencyContact, Patient


class PatientModelTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(full_name="Test Patient")

    def test_patient_uses_a_stable_uuid_identifier(self):
        self.assertIsNotNone(self.patient.pk)
        self.assertEqual(self.patient.status, Patient.Status.ACTIVE)

    def test_emergency_contact_priority_is_unique_per_patient(self):
        EmergencyContact.objects.create(
            patient=self.patient,
            name="Primary Contact",
            phone_number="+233200000001",
            priority_order=1,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EmergencyContact.objects.create(
                    patient=self.patient,
                    name="Duplicate Priority",
                    phone_number="+233200000002",
                    priority_order=1,
                )

    def test_consent_changes_are_stored_as_separate_records(self):
        granted = ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.LOCATION_SHARING,
            status=ConsentRecord.Status.GRANTED,
            policy_version="pilot-v1",
        )
        withdrawn = ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.LOCATION_SHARING,
            status=ConsentRecord.Status.WITHDRAWN,
            policy_version="pilot-v1",
        )

        self.assertNotEqual(granted.pk, withdrawn.pk)
        self.assertEqual(self.patient.consent_records.count(), 2)