from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.patients.models import Patient


class PatientApiAccessTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.patient = Patient.objects.create(full_name="Patient One")
        self.other_patient = Patient.objects.create(full_name="Patient Two")
        self.coordinator = user_model.objects.create_user(
            username="coordinator",
            password="test-password",
        )
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.patient_user = user_model.objects.create_user(
            username="patient-one",
            password="test-password",
        )
        AccountProfile.objects.create(
            user=self.patient_user,
            patient=self.patient,
            role=AccountProfile.Role.PATIENT,
        )

    def test_coordinator_can_list_patient_records(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/patients/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        audit = AuditLog.objects.get(action="patient.list")
        self.assertEqual(audit.actor, self.coordinator)
        self.assertEqual(audit.resource_type, "patient")
        self.assertEqual(audit.metadata, {"result_count": 2})
        self.assertNotIn("Patient One", str(audit.metadata))

    def test_patient_can_only_read_their_own_record(self):
        self.client.force_authenticate(self.patient_user)

        own_response = self.client.get(f"/api/v1/patients/{self.patient.pk}/")
        other_response = self.client.get(f"/api/v1/patients/{self.other_patient.pk}/")

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 404)
        accessed = AuditLog.objects.get(action="patient.read")
        denied = AuditLog.objects.get(action="patient.access_denied")
        self.assertEqual(accessed.actor, self.patient_user)
        self.assertEqual(accessed.resource_id, str(self.patient.pk))
        self.assertEqual(denied.actor, self.patient_user)
        self.assertEqual(denied.resource_id, str(self.other_patient.pk))
        self.assertEqual(denied.outcome, AuditLog.Outcome.DENIED)

    def test_patient_cannot_edit_their_record(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.patch(
            f"/api/v1/patients/{self.patient.pk}/",
            {"full_name": "Changed Name"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)