import uuid
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.devices.models import Device
from apps.monitoring.models import Measurement, PatientLocation
from apps.patients.models import ConsentRecord, EmergencyContact, Patient, PatientDataRequest


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

    def test_patient_cannot_create_patient_records(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/patients/",
            {"full_name": "Unauthorized Patient"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Patient.objects.filter(full_name="Unauthorized Patient").exists())

    def test_coordinator_can_create_patient_record_and_audit_it(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            "/api/v1/patients/",
            {"full_name": "Newly Enrolled Patient", "phone_number": "+233200000020"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["full_name"], "Newly Enrolled Patient")
        self.assertTrue(AuditLog.objects.filter(action="patient.created", actor=self.coordinator).exists())

    def test_patient_detail_includes_contacts_and_consent_history(self):
        EmergencyContact.objects.create(
            patient=self.patient,
            name="Ama Mensah",
            relationship="Sister",
            phone_number="+233201111111",
            notification_preferences={"sms": True},
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
            status=ConsentRecord.Status.GRANTED,
            policy_version="2026-10",
            recorded_by=self.coordinator,
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.get(f"/api/v1/patients/{self.patient.pk}/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["emergency_contacts"]), 1)
        self.assertEqual(body["emergency_contacts"][0]["name"], "Ama Mensah")
        self.assertEqual(body["emergency_contacts"][0]["verification_status"], "verified")
        self.assertEqual(len(body["consent_records"]), 1)
        self.assertEqual(body["consent_records"][0]["scope"], "emergency_contacts")
        self.assertEqual(body["consent_records"][0]["status"], "granted")

    def test_patient_measurements_endpoint_returns_recent_readings(self):
        now = timezone.now()
        Measurement.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            measurement_type=Measurement.Type.HEART_RATE,
            value="88",
            unit="bpm",
            source=Measurement.Source.MANUAL,
            quality=Measurement.Quality.ACCEPTABLE,
            measured_at=now - timezone.timedelta(minutes=5),
        )
        latest = Measurement.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            measurement_type=Measurement.Type.SPO2,
            value="96",
            unit="percent",
            source=Measurement.Source.MANUAL,
            quality=Measurement.Quality.ACCEPTABLE,
            measured_at=now,
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.get(f"/api/v1/patients/{self.patient.pk}/measurements/?limit=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], str(latest.pk))

    def test_patient_locations_endpoint_returns_recent_locations(self):
        now = timezone.now()
        PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude="5.6000",
            longitude="-0.1870",
            accuracy_meters="18",
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=now - timezone.timedelta(minutes=3),
        )
        latest = PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude="5.6002",
            longitude="-0.1868",
            accuracy_meters="12",
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=now,
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.get(f"/api/v1/patients/{self.patient.pk}/locations/?limit=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], str(latest.pk))

    def test_patient_devices_endpoint_returns_device_health(self):
        now = timezone.now()
        Device.objects.create(
            patient=self.patient,
            device_identifier="NS-PATIENT-100",
            device_type=Device.Type.WEARABLE,
            status=Device.Status.ACTIVE,
            battery_percent=76,
            firmware_version="v1.0.1",
            last_seen_at=now,
        )
        stale = Device.objects.create(
            patient=self.patient,
            device_identifier="NS-PATIENT-101",
            device_type=Device.Type.WEARABLE,
            status=Device.Status.INACTIVE,
            last_seen_at=now - timezone.timedelta(minutes=8),
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.get(f"/api/v1/patients/{self.patient.pk}/devices/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        stale_payload = [item for item in payload if item["id"] == str(stale.pk)][0]
        self.assertTrue(stale_payload["is_stale"])
        self.assertIsNone(stale_payload["credential_revoked"])


class PatientDataRequestApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.patient = Patient.objects.create(
            full_name="Patient Request One",
            phone_number="+233200000010",
            relevant_medical_notes="Sensitive notes",
        )
        self.patient_user = user_model.objects.create_user(username="patient-requester")
        AccountProfile.objects.create(user=self.patient_user, patient=self.patient, role=AccountProfile.Role.PATIENT)
        self.coordinator = user_model.objects.create_user(username="request-coordinator")
        AccountProfile.objects.create(user=self.coordinator, role=AccountProfile.Role.EMERGENCY_COORDINATOR)
        EmergencyContact.objects.create(
            patient=self.patient,
            name="Request Contact",
            phone_number="+233200000011",
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
            status=ConsentRecord.Status.GRANTED,
            policy_version="pilot-v1",
        )

    def test_patient_can_request_own_export(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/patient-data-requests/",
            {"request_type": PatientDataRequest.RequestType.ACCESS_EXPORT},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data_request = PatientDataRequest.objects.get()
        self.assertEqual(data_request.patient, self.patient)
        self.assertEqual(data_request.requested_by, self.patient_user)
        self.assertEqual(data_request.request_type, PatientDataRequest.RequestType.ACCESS_EXPORT)

    def test_patient_cannot_request_another_patient_data(self):
        other_patient = Patient.objects.create(full_name="Other Patient")
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/patient-data-requests/",
            {
                "patient": str(other_patient.pk),
                "request_type": PatientDataRequest.RequestType.ACCESS_EXPORT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PatientDataRequest.objects.count(), 0)

    def test_staff_can_approve_and_fulfill_deletion_request(self):
        request = PatientDataRequest.objects.create(
            patient=self.patient,
            requested_by=self.patient_user,
            request_type=PatientDataRequest.RequestType.DELETION,
        )
        self.client.force_authenticate(self.coordinator)

        approved = self.client.post(f"/api/v1/patient-data-requests/{request.pk}/approve/", {"notes": "Approved"}, format="json")
        fulfilled = self.client.post(f"/api/v1/patient-data-requests/{request.pk}/fulfill/")

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(fulfilled.status_code, 200)
        request.refresh_from_db()
        self.patient.refresh_from_db()
        self.assertEqual(request.status, PatientDataRequest.Status.FULFILLED)
        self.assertEqual(self.patient.full_name, "Redacted Patient")
        self.assertEqual(self.patient.phone_number, "")
        self.assertEqual(self.patient.relevant_medical_notes, "")
        self.assertEqual(self.patient.status, Patient.Status.INACTIVE)
        self.assertEqual(self.patient.emergency_contacts.count(), 0)
        self.assertEqual(self.patient.consent_records.count(), 0)

    @override_settings(PATIENT_DATA_REQUEST_RETENTION_DAYS=365)
    def test_prune_patient_data_requests_removes_old_fulfilled_requests(self):
        request = PatientDataRequest.objects.create(
            patient=self.patient,
            requested_by=self.patient_user,
            request_type=PatientDataRequest.RequestType.ACCESS_EXPORT,
            status=PatientDataRequest.Status.FULFILLED,
        )
        PatientDataRequest.objects.filter(pk=request.pk).update(updated_at=timezone.now() - timezone.timedelta(days=500))
        output = StringIO()

        call_command("prune_patient_data_requests", stdout=output)

        self.assertIn("Deleted", output.getvalue())
        self.assertFalse(PatientDataRequest.objects.filter(pk=request.pk).exists())

    def test_prune_patient_data_requests_rejects_invalid_days(self):
        with self.assertRaises(CommandError):
            call_command("prune_patient_data_requests", "--days", "0")