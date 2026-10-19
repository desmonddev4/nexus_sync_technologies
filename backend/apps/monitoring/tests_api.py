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

    def test_measurement_below_rule_threshold_is_recorded_as_no_match(self):
        rule = self.create_reviewed_rule()
        measurement = self.create_acceptable_measurement(value="82")

        evaluation = evaluate_measurement_against_rule(measurement=measurement, rule_id=rule.pk)

        self.assertEqual(evaluation.status, MonitoringRuleEvaluation.Status.NO_MATCH)
        self.assertEqual(evaluation.details["threshold"], "100.00")
        self.assertEqual(evaluation.details["consecutive_readings_found"], 1)
        self.assertIsNone(evaluation.incident_id)
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


class MonitoringRuleManagementApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.coordinator = user_model.objects.create_user(username="ops-coordinator")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.clinician = user_model.objects.create_user(username="ops-clinician")
        AccountProfile.objects.create(
            user=self.clinician,
            role=AccountProfile.Role.CLINICIAN,
        )
        self.patient_user = user_model.objects.create_user(username="ops-patient")
        AccountProfile.objects.create(
            user=self.patient_user,
            role=AccountProfile.Role.PATIENT,
        )

    def test_operations_staff_can_list_rules(self):
        rule = MonitoringRule.objects.create(
            name="High HR",
            measurement_type=Measurement.Type.HEART_RATE,
            operator=MonitoringRule.Operator.GREATER_THAN,
            threshold="100",
            priority=MonitoringRule.Priority.HIGH,
            version="v1",
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.get("/api/v1/monitoring/rules/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], str(rule.pk))

    def test_non_operations_role_cannot_list_rules(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.get("/api/v1/monitoring/rules/")

        self.assertEqual(response.status_code, 403)

    def test_clinician_can_create_rule(self):
        self.client.force_authenticate(self.clinician)

        response = self.client.post(
            "/api/v1/monitoring/rules/",
            {
                "name": "Low SpO2",
                "description": "Alert if oxygen is low",
                "measurement_type": Measurement.Type.SPO2,
                "operator": MonitoringRule.Operator.LESS_THAN,
                "threshold": "92",
                "priority": MonitoringRule.Priority.CRITICAL,
                "minimum_consecutive_readings": 2,
                "lookback_window_seconds": 300,
                "include_simulated": False,
                "version": "v1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["is_enabled"])

    def test_coordinator_cannot_create_rule(self):
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            "/api/v1/monitoring/rules/",
            {
                "name": "Rule",
                "measurement_type": Measurement.Type.HEART_RATE,
                "operator": MonitoringRule.Operator.GREATER_THAN,
                "threshold": "100",
                "priority": MonitoringRule.Priority.HIGH,
                "minimum_consecutive_readings": 1,
                "lookback_window_seconds": 300,
                "include_simulated": True,
                "version": "v1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_clinician_can_review_enable_rule(self):
        rule = MonitoringRule.objects.create(
            name="Enable Me",
            measurement_type=Measurement.Type.HEART_RATE,
            operator=MonitoringRule.Operator.GREATER_THAN,
            threshold="100",
            priority=MonitoringRule.Priority.HIGH,
            version="v1",
        )
        self.client.force_authenticate(self.clinician)

        response = self.client.post(
            f"/api/v1/monitoring/rules/{rule.pk}/review/",
            {"is_enabled": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        rule.refresh_from_db()
        self.assertTrue(rule.is_enabled)
        self.assertEqual(rule.reviewed_by, self.clinician)
        self.assertIsNotNone(rule.reviewed_at)

    def test_evaluated_rule_version_cannot_be_modified(self):
        patient = Patient.objects.create(full_name="Rule Patient")
        rule = MonitoringRule.objects.create(
            name="Immutable",
            measurement_type=Measurement.Type.HEART_RATE,
            operator=MonitoringRule.Operator.GREATER_THAN,
            threshold="100",
            priority=MonitoringRule.Priority.HIGH,
            version="v1",
            is_enabled=True,
            reviewed_by=self.clinician,
            reviewed_at=timezone.now(),
        )
        measurement = Measurement.objects.create(
            patient=patient,
            event_id=uuid.uuid4(),
            measurement_type=Measurement.Type.HEART_RATE,
            value="130",
            unit="bpm",
            source=Measurement.Source.MANUAL,
            quality=Measurement.Quality.ACCEPTABLE,
            measured_at=timezone.now(),
        )
        MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.NO_MATCH,
            details={},
        )
        self.client.force_authenticate(self.clinician)

        response = self.client.patch(
            f"/api/v1/monitoring/rules/{rule.pk}/",
            {"threshold": "120"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class MeasurementQualityReviewApiTests(APITestCase):
    def setUp(self):
        self.patient = Patient.objects.create(full_name="Quality Review Patient")
        self.measurement = Measurement.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            measurement_type=Measurement.Type.HEART_RATE,
            value="82",
            unit="bpm",
            source=Measurement.Source.SIMULATOR,
            measured_at=timezone.now(),
        )
        user_model = get_user_model()
        self.clinician = user_model.objects.create_user(username="quality-clinician")
        AccountProfile.objects.create(user=self.clinician, role=AccountProfile.Role.CLINICIAN)
        self.coordinator = user_model.objects.create_user(username="quality-coordinator")
        AccountProfile.objects.create(user=self.coordinator, role=AccountProfile.Role.EMERGENCY_COORDINATOR)
        self.patient_user = user_model.objects.create_user(username="quality-patient")
        AccountProfile.objects.create(user=self.patient_user, patient=self.patient, role=AccountProfile.Role.PATIENT)

    def test_clinician_can_list_unreviewed_quality_queue(self):
        self.client.force_authenticate(self.clinician)
        response = self.client.get("/api/v1/measurements/review/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["patient_name"], self.patient.full_name)
        self.assertEqual(response.json()[0]["quality"], Measurement.Quality.UNREVIEWED)

    def test_coordinator_and_patient_cannot_review_measurements(self):
        for user in (self.coordinator, self.patient_user):
            self.client.force_authenticate(user)
            response = self.client.get("/api/v1/measurements/review/")
            self.assertEqual(response.status_code, 403)

    def test_clinician_can_accept_measurement_and_decision_is_audited(self):
        self.client.force_authenticate(self.clinician)
        response = self.client.post(
            f"/api/v1/measurements/{self.measurement.pk}/review/",
            {"quality": Measurement.Quality.ACCEPTABLE},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.quality, Measurement.Quality.ACCEPTABLE)
        self.assertEqual(self.measurement.quality_reviewed_by, self.clinician)
        self.assertIsNotNone(self.measurement.quality_reviewed_at)
        audit = AuditLog.objects.get(action="measurement.quality_reviewed")
        self.assertEqual(audit.actor, self.clinician)
        self.assertEqual(audit.resource_id, str(self.measurement.pk))

    def test_measurement_review_decision_cannot_be_overwritten(self):
        self.client.force_authenticate(self.clinician)
        first = self.client.post(
            f"/api/v1/measurements/{self.measurement.pk}/review/",
            {"quality": Measurement.Quality.QUESTIONABLE},
            format="json",
        )
        second = self.client.post(
            f"/api/v1/measurements/{self.measurement.pk}/review/",
            {"quality": Measurement.Quality.ACCEPTABLE},
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.quality, Measurement.Quality.QUESTIONABLE)

    def test_accepting_measurement_evaluates_enabled_rules(self):
        rule = MonitoringRule.objects.create(
            name="Accepted reading check",
            measurement_type=Measurement.Type.HEART_RATE,
            operator=MonitoringRule.Operator.GREATER_THAN,
            threshold="100",
            priority=MonitoringRule.Priority.HIGH,
            version="v1",
            is_enabled=True,
            reviewed_by=self.clinician,
            reviewed_at=timezone.now(),
            include_simulated=True,
        )
        self.measurement.value = "120"
        self.measurement.save(update_fields=("value", "updated_at"))
        self.client.force_authenticate(self.clinician)

        response = self.client.post(
            f"/api/v1/measurements/{self.measurement.pk}/review/",
            {"quality": Measurement.Quality.ACCEPTABLE},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        evaluation = MonitoringRuleEvaluation.objects.get(rule=rule, measurement=self.measurement)
        self.assertEqual(evaluation.status, MonitoringRuleEvaluation.Status.TRIGGERED)
        self.assertEqual(evaluation.incident.trigger_source, Incident.Source.RULE)