import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.devices.models import Device, DeviceCredential
from apps.incidents.models import Incident, IncidentEvent
from apps.monitoring.models import (
    Measurement,
    MonitoringRule,
    MonitoringRuleEvaluation,
    PatientLocation,
)
from apps.monitoring.services import evaluate_measurement_against_rule
from apps.patients.models import Patient


class MonitoringIngestApiTests(APITestCase):
    def setUp(self):
        self.patient = Patient.objects.create(full_name="Monitoring Patient")
        self.other_patient = Patient.objects.create(full_name="Other Patient")
        user = get_user_model().objects.create_user(username="patient")
        AccountProfile.objects.create(
            user=user,
            patient=self.patient,
            role=AccountProfile.Role.PATIENT,
        )
        self.client.force_authenticate(user)
        self.measured_at = "2026-10-17T18:00:00Z"

    def create_reviewed_rule(self, **overrides):
        clinician = get_user_model().objects.create_user(username=f"clinician-{uuid.uuid4()}")
        AccountProfile.objects.create(user=clinician, role=AccountProfile.Role.CLINICIAN)
        now = timezone.now()
        values = {
            "name": "High heart rate review rule",
            "measurement_type": Measurement.Type.HEART_RATE,
            "operator": MonitoringRule.Operator.GREATER_THAN,
            "threshold": "100",
            "priority": MonitoringRule.Priority.HIGH,
            "is_enabled": True,
            "version": "pilot-v1",
            "reviewed_by": clinician,
            "reviewed_at": now,
        }
        values.update(overrides)
        return MonitoringRule.objects.create(**values)

    def create_acceptable_measurement(self, *, value, measured_at=None, source=None):
        return Measurement.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            measurement_type=Measurement.Type.HEART_RATE,
            value=value,
            unit="bpm",
            source=source or Measurement.Source.MANUAL,
            quality=Measurement.Quality.ACCEPTABLE,
            measured_at=measured_at or timezone.now(),
        )

    def test_measurement_retry_does_not_duplicate_data(self):
        event_id = str(uuid.uuid4())
        payload = {
            "patient": str(self.patient.pk),
            "event_id": event_id,
            "measurement_type": Measurement.Type.HEART_RATE,
            "value": "82",
            "unit": "bpm",
            "source": Measurement.Source.SIMULATOR,
            "measured_at": self.measured_at,
        }

        first = self.client.post("/api/v1/measurements/", payload, format="json")
        retry = self.client.post("/api/v1/measurements/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertEqual(Measurement.objects.count(), 1)

    def test_unreviewed_measurement_is_logged_but_does_not_trigger_rule(self):
        rule = self.create_reviewed_rule(include_simulated=True)
        event_id = str(uuid.uuid4())
        payload = {
            "patient": str(self.patient.pk),
            "event_id": event_id,
            "measurement_type": Measurement.Type.HEART_RATE,
            "value": "125",
            "unit": "bpm",
            "source": Measurement.Source.SIMULATOR,
            "measured_at": timezone.now().isoformat(),
        }

        first = self.client.post("/api/v1/measurements/", payload, format="json")
        retry = self.client.post("/api/v1/measurements/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        evaluation = MonitoringRuleEvaluation.objects.get(rule=rule)
        self.assertEqual(evaluation.status, MonitoringRuleEvaluation.Status.QUALITY_REJECTED)
        self.assertEqual(Incident.objects.count(), 0)
        self.assertEqual(MonitoringRuleEvaluation.objects.count(), 1)

    def test_consecutive_acceptable_readings_create_one_audited_incident(self):
        rule = self.create_reviewed_rule(
            minimum_consecutive_readings=2,
            include_simulated=True,
        )
        first = self.create_acceptable_measurement(
            value="125",
            measured_at=timezone.now() - timezone.timedelta(minutes=1),
            source=Measurement.Source.SIMULATOR,
        )
        first_evaluation = evaluate_measurement_against_rule(measurement=first, rule_id=rule.pk)
        self.assertEqual(
            first_evaluation.status,
            MonitoringRuleEvaluation.Status.INSUFFICIENT_READINGS,
        )

        second = self.create_acceptable_measurement(
            value="130",
            source=Measurement.Source.SIMULATOR,
        )
        triggered = evaluate_measurement_against_rule(measurement=second, rule_id=rule.pk)
        repeated_evaluation = evaluate_measurement_against_rule(
            measurement=second,
            rule_id=rule.pk,
        )

        self.assertEqual(triggered.status, MonitoringRuleEvaluation.Status.TRIGGERED)
        self.assertEqual(repeated_evaluation.pk, triggered.pk)
        self.assertEqual(triggered.incident.incident_type, Incident.Type.MEASUREMENT_ALERT)
        self.assertEqual(triggered.incident.trigger_source, Incident.Source.RULE)
        self.assertEqual(triggered.incident.priority, Incident.Priority.HIGH)
        self.assertEqual(triggered.incident.events.count(), 1)
        self.client.force_authenticate(rule.reviewed_by)
        timeline = self.client.get(f"/api/v1/incidents/{triggered.incident_id}/events/")
        self.assertEqual(timeline.status_code, 200)
        evidence = timeline.json()[0]["details"]
        self.assertEqual(evidence["rule_id"], str(rule.pk))
        self.assertEqual(evidence["rule_version"], rule.version)
        self.assertEqual(evidence["measurement_id"], str(second.pk))
        self.assertEqual(evidence["measurement_source"], Measurement.Source.SIMULATOR)
        access_log = AuditLog.objects.get(action="incident.events.accessed")
        self.assertEqual(access_log.actor, rule.reviewed_by)
        self.assertEqual(access_log.resource_id, str(triggered.incident_id))
        self.assertEqual(access_log.metadata, {})

        third = self.create_acceptable_measurement(
            value="132",
            source=Measurement.Source.SIMULATOR,
        )
        linked = evaluate_measurement_against_rule(measurement=third, rule_id=rule.pk)

        self.assertEqual(linked.status, MonitoringRuleEvaluation.Status.LINKED_TO_ACTIVE_INCIDENT)
        self.assertEqual(linked.incident_id, triggered.incident_id)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(
            IncidentEvent.objects.filter(
                incident=triggered.incident,
                event_type=IncidentEvent.Type.EVIDENCE_RECORDED,
            ).count(),
            1,
        )

    def test_simulated_reading_is_skipped_unless_rule_explicitly_allows_it(self):
        rule = self.create_reviewed_rule(include_simulated=False)
        measurement = self.create_acceptable_measurement(
            value="125",
            source=Measurement.Source.SIMULATOR,
        )

        evaluation = evaluate_measurement_against_rule(measurement=measurement, rule_id=rule.pk)

        self.assertEqual(evaluation.status, MonitoringRuleEvaluation.Status.SIMULATED_SKIPPED)
        self.assertEqual(Incident.objects.count(), 0)

    def test_stale_measurement_cannot_trigger_a_rule(self):
        rule = self.create_reviewed_rule()
        measurement = self.create_acceptable_measurement(
            value="125",
            measured_at=timezone.now() - timezone.timedelta(minutes=8),
        )

        evaluation = evaluate_measurement_against_rule(measurement=measurement, rule_id=rule.pk)

        self.assertEqual(evaluation.status, MonitoringRuleEvaluation.Status.STALE_READING)
        self.assertEqual(Incident.objects.count(), 0)

    def test_patient_cannot_submit_measurement_for_another_patient(self):
        response = self.client.post(
            "/api/v1/measurements/",
            {
                "patient": str(self.other_patient.pk),
                "event_id": str(uuid.uuid4()),
                "measurement_type": Measurement.Type.HEART_RATE,
                "value": "82",
                "unit": "bpm",
                "source": Measurement.Source.SIMULATOR,
                "measured_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_spo2_and_unit_values_are_validated(self):
        response = self.client.post(
            "/api/v1/measurements/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(uuid.uuid4()),
                "measurement_type": Measurement.Type.SPO2,
                "value": "101",
                "unit": "percent",
                "source": Measurement.Source.SIMULATOR,
                "measured_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_out_of_range_location_is_rejected(self):
        response = self.client.post(
            "/api/v1/locations/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(uuid.uuid4()),
                "latitude": "91",
                "longitude": "-0.187",
                "accuracy_meters": "12",
                "source": PatientLocation.Source.SIMULATOR,
                "recorded_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PatientLocation.objects.count(), 0)

    def test_user_token_cannot_submit_wearable_originated_data(self):
        device = Device.objects.create(
            device_identifier="NS-MONITOR-001",
            device_type=Device.Type.WEARABLE,
            patient=self.patient,
        )
        response = self.client.post(
            "/api/v1/measurements/",
            {
                "patient": str(self.patient.pk),
                "device": str(device.pk),
                "event_id": str(uuid.uuid4()),
                "measurement_type": Measurement.Type.HEART_RATE,
                "value": "82",
                "unit": "bpm",
                "source": Measurement.Source.WEARABLE,
                "measured_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_device_credentials_ingest_wearable_data_and_set_source_server_side(self):
        device = Device.objects.create(
            device_identifier="NS-AUTHENTICATED-001",
            device_type=Device.Type.WEARABLE,
            patient=self.patient,
            status=Device.Status.ACTIVE,
        )
        secret = DeviceCredential.issue(device)
        client = self.client.__class__()
        client.credentials(
            HTTP_AUTHORIZATION=f"Device {device.device_identifier}:{secret}"
        )

        response = client.post(
            "/api/v1/measurements/",
            {
                "event_id": str(uuid.uuid4()),
                "measurement_type": Measurement.Type.HEART_RATE,
                "value": "82",
                "unit": "bpm",
                "measured_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        measurement = Measurement.objects.get()
        self.assertEqual(measurement.patient, self.patient)
        self.assertEqual(measurement.device, device)
        self.assertEqual(measurement.source, Measurement.Source.WEARABLE)
        self.assertIsNone(measurement.recorded_by)

    def test_revoked_device_credential_cannot_ingest(self):
        device = Device.objects.create(
            device_identifier="NS-REVOKED-001",
            device_type=Device.Type.WEARABLE,
            patient=self.patient,
            status=Device.Status.ACTIVE,
        )
        secret = DeviceCredential.issue(device)
        credential = DeviceCredential.objects.get(device=device)
        credential.revoked_at = timezone.now()
        credential.save(update_fields=("revoked_at", "updated_at"))
        client = self.client.__class__()
        client.credentials(
            HTTP_AUTHORIZATION=f"Device {device.device_identifier}:{secret}"
        )

        response = client.post(
            "/api/v1/measurements/",
            {
                "event_id": str(uuid.uuid4()),
                "measurement_type": Measurement.Type.HEART_RATE,
                "value": "82",
                "unit": "bpm",
                "measured_at": self.measured_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Measurement.objects.count(), 0)