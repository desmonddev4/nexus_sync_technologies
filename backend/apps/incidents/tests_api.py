import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase
from django.utils import timezone

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.devices.models import Device, DeviceCredential
from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider
from apps.incidents.models import Incident, IncidentEvent
from apps.incidents.models import IncidentLocationSnapshot, IncidentRoute
from apps.incidents.services import create_sos_incident, transition_incident
from apps.monitoring.models import PatientLocation
from apps.emergency_services.routing import RouteCalculationError, RouteConfigurationError, RouteResult
from apps.notifications.models import IncidentNotification, NotificationEvent
from apps.patients.models import ConsentRecord, EmergencyContact, Patient


class SOSApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.patient = Patient.objects.create(full_name="SOS Patient")
        self.patient_user = user_model.objects.create_user(username="patient")
        AccountProfile.objects.create(
            user=self.patient_user,
            patient=self.patient,
            role=AccountProfile.Role.PATIENT,
        )
        self.coordinator = user_model.objects.create_user(username="operator")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.event_id = uuid.uuid4()

    def create_acknowledged_incident(self):
        return Incident.objects.create(
            patient=self.patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
            status=Incident.Status.ACKNOWLEDGED,
        )

    def create_vehicle(self, *, simulated=False, **overrides):
        provider_status = (
            EmergencyProvider.VerificationStatus.SIMULATED
            if simulated
            else EmergencyProvider.VerificationStatus.VERIFIED
        )
        provider = EmergencyProvider.objects.create(
            name="Simulated Dispatch Provider" if simulated else "Verified Dispatch Provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=provider_status,
            fleet_feed_authorized=True,
        )
        values = {
            "provider": provider,
            "vehicle_identifier": "NS-ASSIGN-001",
            "availability": AmbulanceVehicle.Availability.AVAILABLE,
            "data_source": (
                AmbulanceVehicle.DataSource.SIMULATOR
                if simulated
                else AmbulanceVehicle.DataSource.PROVIDER
            ),
            "latitude": Decimal("5.6037"),
            "longitude": Decimal("-0.1870"),
            "location_updated_at": timezone.now(),
        }
        values.update(overrides)
        return AmbulanceVehicle.objects.create(**values)

    def test_retried_sos_returns_the_original_incident(self):
        self.client.force_authenticate(self.patient_user)
        payload = {
            "patient": str(self.patient.pk),
            "event_id": str(self.event_id),
            "trigger_source": Incident.Source.MANUAL,
        }

        first = self.client.post("/api/v1/incidents/sos/", payload, format="json")
        retry = self.client.post("/api/v1/incidents/sos/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(IncidentEvent.objects.count(), 1)

    def test_authenticated_simulator_can_raise_idempotent_sos_without_client_patient_id(self):
        device = Device.objects.create(
            device_identifier="NS-SOS-SIM-001",
            device_type=Device.Type.SIMULATOR,
            patient=self.patient,
            status=Device.Status.ACTIVE,
        )
        secret = DeviceCredential.issue(device)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device.device_identifier}:{secret}")
        payload = {"event_id": str(self.event_id), "trigger_source": Incident.Source.SIMULATOR}

        first = self.client.post("/api/v1/incidents/sos/", payload, format="json")
        retry = self.client.post("/api/v1/incidents/sos/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(Incident.objects.get().patient, self.patient)

    def test_wearable_sos_is_attributed_to_wearable_and_cannot_claim_simulator_source(self):
        device = Device.objects.create(
            device_identifier="NS-SOS-WEAR-001",
            device_type=Device.Type.WEARABLE,
            patient=self.patient,
            status=Device.Status.ACTIVE,
        )
        secret = DeviceCredential.issue(device)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device.device_identifier}:{secret}")

        rejected = self.client.post(
            "/api/v1/incidents/sos/",
            {"event_id": str(self.event_id), "trigger_source": Incident.Source.SIMULATOR},
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(Incident.objects.count(), 0)

        accepted = self.client.post(
            "/api/v1/incidents/sos/",
            {"event_id": str(self.event_id), "trigger_source": Incident.Source.WEARABLE},
            format="json",
        )
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(accepted.json()["trigger_source"], Incident.Source.WEARABLE)

    def test_sos_captures_latest_received_location_snapshot(self):
        recorded_at = timezone.now() - timedelta(minutes=2)
        location = PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude=Decimal("5.603700"),
            longitude=Decimal("-0.187000"),
            accuracy_meters=Decimal("12.50"),
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=recorded_at,
        )
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(self.event_id),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["location"]["latitude"], "5.603700")
        self.assertEqual(response.json()["location"]["accuracy_meters"], "12.50")
        self.assertEqual(response.json()["location"]["source"], PatientLocation.Source.PHONE)
        self.assertFalse(response.json()["location"]["is_stale"])
        self.assertEqual(
            parse_datetime(response.json()["location"]["recorded_at"]),
            location.recorded_at,
        )

        PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude=Decimal("5.700000"),
            longitude=Decimal("-0.200000"),
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=timezone.now(),
        )
        retry = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(self.event_id),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["location"]["latitude"], "5.603700")

    def test_old_location_snapshot_is_explicitly_stale(self):
        PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude=Decimal("5.603700"),
            longitude=Decimal("-0.187000"),
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=timezone.now() - timedelta(minutes=8),
        )
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(self.event_id),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["location"]["is_stale"])
        self.assertGreater(response.json()["location"]["age_seconds"], 300)

    def test_sos_without_location_returns_no_fabricated_location(self):
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(self.event_id),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["location"])

    def test_patient_cannot_raise_sos_for_another_patient(self):
        another_patient = Patient.objects.create(full_name="Other Patient")
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(another_patient.pk),
                "event_id": str(uuid.uuid4()),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Incident.objects.count(), 0)

    def test_only_staff_can_acknowledge(self):
        incident = Incident.objects.create(
            patient=self.patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
        )
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/acknowledge/")

        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.coordinator)
        response = self.client.post(f"/api/v1/incidents/{incident.pk}/acknowledge/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Incident.Status.ACKNOWLEDGED)

    def test_incident_list_and_acknowledgement_permissions_by_role(self):
        incident = Incident.objects.create(
            patient=self.patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
        )
        clinician = get_user_model().objects.create_user(username="incident-clinician")
        AccountProfile.objects.create(user=clinician, role=AccountProfile.Role.CLINICIAN)
        responder = get_user_model().objects.create_user(username="incident-responder")
        AccountProfile.objects.create(user=responder, role=AccountProfile.Role.PROVIDER_RESPONDER)
        contact = get_user_model().objects.create_user(username="incident-contact")
        AccountProfile.objects.create(user=contact, role=AccountProfile.Role.EMERGENCY_CONTACT)
        superuser = get_user_model().objects.create_superuser(
            username="incident-superuser",
            email="incident-superuser@example.test",
            password="test-password",
        )
        url = f"/api/v1/incidents/{incident.pk}/"

        role_cases = (
            (self.patient_user, 200, 1, 403),
            (clinician, 200, 1, 200),
            (self.coordinator, 200, 1, 200),
            (responder, 403, 0, 403),
            (contact, 403, 0, 403),
            (superuser, 200, 1, 200),
        )
        for user, list_status, visible_count, acknowledge_status in role_cases:
            with self.subTest(role=user.username):
                self.client.force_authenticate(user)
                listed = self.client.get("/api/v1/incidents/")
                self.assertEqual(listed.status_code, list_status)
                if list_status == 200:
                    self.assertEqual(len(listed.json()), visible_count)
                acknowledged = self.client.post(f"{url}acknowledge/")
                self.assertEqual(acknowledged.status_code, acknowledge_status)
                if acknowledge_status == 200:
                    incident.refresh_from_db()
                    incident.status = Incident.Status.CREATED
                    incident.save(update_fields=("status", "updated_at"))

    def test_sos_queues_only_verified_contacts_with_current_consent(self):
        contact = EmergencyContact.objects.create(
            patient=self.patient,
            name="Verified Contact",
            phone_number="+233200000001",
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        EmergencyContact.objects.create(
            patient=self.patient,
            name="Unverified Contact",
            phone_number="+233200000002",
            priority_order=2,
        )
        ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
            status=ConsentRecord.Status.GRANTED,
            policy_version="pilot-v1",
        )
        self.client.force_authenticate(self.patient_user)
        payload = {
            "patient": str(self.patient.pk),
            "event_id": str(uuid.uuid4()),
            "trigger_source": Incident.Source.MANUAL,
        }

        first = self.client.post("/api/v1/incidents/sos/", payload, format="json")
        retry = self.client.post("/api/v1/incidents/sos/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(IncidentNotification.objects.count(), 1)
        notification = IncidentNotification.objects.get()
        self.assertEqual(notification.emergency_contact, contact)
        self.assertEqual(notification.recipient_address_snapshot, contact.phone_number)
        self.assertEqual(notification.status, IncidentNotification.Status.QUEUED)
        self.assertEqual(NotificationEvent.objects.count(), 1)

    def test_latest_withdrawn_consent_prevents_contact_notification_queueing(self):
        EmergencyContact.objects.create(
            patient=self.patient,
            name="Verified Contact",
            phone_number="+233200000001",
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        for consent_status in (ConsentRecord.Status.GRANTED, ConsentRecord.Status.WITHDRAWN):
            ConsentRecord.objects.create(
                patient=self.patient,
                scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
                status=consent_status,
                policy_version="pilot-v1",
            )
        self.client.force_authenticate(self.patient_user)

        response = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(uuid.uuid4()),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(IncidentNotification.objects.count(), 0)

    def test_notification_status_is_staff_only_and_redacts_phone_number(self):
        contact = EmergencyContact.objects.create(
            patient=self.patient,
            name="Verified Contact",
            phone_number="+233200000001",
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
            status=ConsentRecord.Status.GRANTED,
            policy_version="pilot-v1",
        )
        incident, _ = create_sos_incident(
            patient=self.patient,
            event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
            actor=self.patient_user,
        )
        notification = IncidentNotification.objects.get(emergency_contact=contact)
        url = f"/api/v1/incidents/{incident.pk}/notifications/"
        self.client.force_authenticate(self.patient_user)

        patient_response = self.client.get(url)

        self.assertEqual(patient_response.status_code, 403)
        denied_audit = AuditLog.objects.get(action="incident.access_denied")
        self.assertEqual(denied_audit.actor, self.patient_user)
        self.assertEqual(denied_audit.resource_id, str(incident.pk))
        self.assertEqual(denied_audit.outcome, AuditLog.Outcome.DENIED)
        self.client.force_authenticate(self.coordinator)
        staff_response = self.client.get(url)

        self.assertEqual(staff_response.status_code, 200)
        self.assertEqual(staff_response.json()[0]["status"], IncidentNotification.Status.QUEUED)
        self.assertNotIn(notification.recipient_address_snapshot, str(staff_response.json()))

    def test_staff_can_assign_vehicle_and_record_operator_reported_dispatch(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle()
        self.client.force_authenticate(self.coordinator)

        assigned = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )
        dispatch_request = self.client.post(
            f"/api/v1/incidents/{incident.pk}/record-dispatch-request/"
        )
        confirmation = self.client.post(
            f"/api/v1/incidents/{incident.pk}/record-dispatch-confirmation/",
            {"confirmation_reference": "Provider call, operator log 0042"},
            format="json",
        )

        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["status"], Incident.Status.RESPONDER_ASSIGNED)
        self.assertEqual(assigned.json()["assigned_vehicle_identifier"], vehicle.vehicle_identifier)
        self.assertFalse(assigned.json()["is_simulated_dispatch"])
        self.assertEqual(dispatch_request.status_code, 200)
        self.assertFalse(dispatch_request.json()["provider_contacted_by_system"])
        self.assertEqual(
            dispatch_request.json()["incident"]["status"],
            Incident.Status.DISPATCH_REQUESTED,
        )
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(
            confirmation.json()["incident"]["status"],
            Incident.Status.DISPATCH_CONFIRMED,
        )
        self.assertEqual(confirmation.json()["confirmation_source"], "operator_reported")
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.current_incident, incident)
        self.assertEqual(vehicle.availability, AmbulanceVehicle.Availability.ON_CALL)

    def test_simulated_assignment_requires_explicit_opt_in_and_remains_labeled(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle(simulated=True)
        self.client.force_authenticate(self.coordinator)

        rejected = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )
        accepted = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk), "include_simulated": True},
            format="json",
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["is_simulated_dispatch"])

    def test_reassignment_releases_the_previous_vehicle(self):
        incident = self.create_acknowledged_incident()
        first_vehicle = self.create_vehicle(vehicle_identifier="NS-ASSIGN-101")
        second_vehicle = self.create_vehicle(vehicle_identifier="NS-ASSIGN-102")
        self.client.force_authenticate(self.coordinator)

        first_assignment = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(first_vehicle.pk)},
            format="json",
        )
        replacement = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(second_vehicle.pk)},
            format="json",
        )

        self.assertEqual(first_assignment.status_code, 200)
        self.assertEqual(replacement.status_code, 200)
        self.assertEqual(replacement.json()["assigned_vehicle"], str(second_vehicle.pk))
        first_vehicle.refresh_from_db()
        second_vehicle.refresh_from_db()
        self.assertIsNone(first_vehicle.current_incident_id)
        self.assertEqual(first_vehicle.availability, AmbulanceVehicle.Availability.AVAILABLE)
        self.assertEqual(second_vehicle.current_incident_id, incident.pk)
        self.assertEqual(second_vehicle.availability, AmbulanceVehicle.Availability.ON_CALL)

    def test_database_rejects_multiple_vehicles_linked_to_one_incident(self):
        incident = self.create_acknowledged_incident()
        first_vehicle = self.create_vehicle(vehicle_identifier="NS-UNIQUE-101")
        second_vehicle = self.create_vehicle(vehicle_identifier="NS-UNIQUE-102")
        first_vehicle.current_incident = incident
        first_vehicle.save(update_fields=("current_incident", "updated_at"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second_vehicle.current_incident = incident
                second_vehicle.save(update_fields=("current_incident", "updated_at"))

    def test_stale_vehicle_cannot_be_assigned(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle(
            location_updated_at=timezone.now() - timedelta(minutes=6),
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        vehicle.refresh_from_db()
        self.assertIsNone(vehicle.current_incident_id)

    def test_patient_cannot_assign_or_record_dispatch(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle()
        self.client.force_authenticate(self.patient_user)

        assignment = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )
        dispatch = self.client.post(
            f"/api/v1/incidents/{incident.pk}/record-dispatch-request/"
        )

        self.assertEqual(assignment.status_code, 403)
        self.assertEqual(dispatch.status_code, 403)

    def test_provider_vehicle_requires_explicit_feed_authorization(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle()
        vehicle.provider.fleet_feed_authorized = False
        vehicle.provider.save(update_fields=("fleet_feed_authorized", "updated_at"))
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not authorized", str(response.json()))

    def test_closing_incident_releases_vehicle(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle(simulated=True)
        self.client.force_authenticate(self.coordinator)
        self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk), "include_simulated": True},
            format="json",
        )
        self.client.post(f"/api/v1/incidents/{incident.pk}/record-dispatch-request/")
        self.client.post(
            f"/api/v1/incidents/{incident.pk}/record-dispatch-confirmation/",
            {"confirmation_reference": "Provider call log"},
            format="json",
        )
        incident.refresh_from_db()
        for status in (
            Incident.Status.RESPONDER_EN_ROUTE,
            Incident.Status.ARRIVED,
            Incident.Status.RESOLVED,
            Incident.Status.CLOSED,
        ):
            response = self.client.post(
                f"/api/v1/incidents/{incident.pk}/status/",
                {"status": status},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            incident.refresh_from_db()

        incident.refresh_from_db()
        vehicle.refresh_from_db()
        self.assertEqual(incident.status, Incident.Status.CLOSED)
        self.assertIsNone(incident.assigned_vehicle_id)
        self.assertTrue(incident.is_simulated_dispatch)
        self.assertIsNone(vehicle.current_incident_id)
        self.assertEqual(vehicle.availability, AmbulanceVehicle.Availability.AVAILABLE)

    def test_dispatch_cannot_be_marked_confirmed_through_generic_status_action(self):
        incident = self.create_acknowledged_incident()
        vehicle = self.create_vehicle()
        self.client.force_authenticate(self.coordinator)
        self.client.post(
            f"/api/v1/incidents/{incident.pk}/assign-responder/",
            {"vehicle": str(vehicle.pk)},
            format="json",
        )
        self.client.post(f"/api/v1/incidents/{incident.pk}/record-dispatch-request/")

        response = self.client.post(
            f"/api/v1/incidents/{incident.pk}/status/",
            {"status": Incident.Status.DISPATCH_CONFIRMED},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        incident.refresh_from_db()
        self.assertEqual(incident.status, Incident.Status.DISPATCH_REQUESTED)

    def prepare_incident_for_route(
        self,
        *,
        patient_location_age_minutes=1,
        vehicle_location_age_minutes=1,
        simulated=False,
    ):
        incident = self.create_acknowledged_incident()
        patient_location_recorded_at = timezone.now() - timedelta(minutes=patient_location_age_minutes)
        IncidentLocationSnapshot.objects.create(
            incident=incident,
            latitude=Decimal("5.603700"),
            longitude=Decimal("-0.187000"),
            accuracy_meters=Decimal("15.00"),
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=patient_location_recorded_at,
            received_at=patient_location_recorded_at,
        )
        vehicle = self.create_vehicle(
            simulated=simulated,
            location_updated_at=timezone.now() - timedelta(minutes=vehicle_location_age_minutes),
            availability=AmbulanceVehicle.Availability.ON_CALL,
        )
        incident.assigned_vehicle = vehicle
        incident.assigned_operator = self.coordinator
        incident.is_simulated_dispatch = simulated
        incident.status = Incident.Status.RESPONDER_ASSIGNED
        incident.save(
            update_fields=(
                "assigned_vehicle",
                "assigned_operator",
                "is_simulated_dispatch",
                "status",
                "updated_at",
            )
        )
        vehicle.current_incident = incident
        vehicle.save(update_fields=("current_incident", "updated_at"))
        return incident, vehicle

    @patch("apps.incidents.views.GoogleRoutesProvider")
    def test_route_action_returns_and_persists_eta(self, provider_class):
        incident, _ = self.prepare_incident_for_route()
        provider_class.return_value.calculate_driving_route.return_value = RouteResult(
            distance_meters=3400,
            duration_seconds=720,
            encoded_polyline="test-polyline",
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/route/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["distance_meters"], 3400)
        self.assertEqual(response.json()["duration_minutes"], 12)
        self.assertFalse(response.json()["is_simulated"])
        self.assertEqual(IncidentRoute.objects.filter(incident=incident).count(), 1)
        self.assertEqual(
            provider_class.return_value.calculate_driving_route.call_args.kwargs["destination"],
            (Decimal("5.603700"), Decimal("-0.187000")),
        )

    @patch("apps.incidents.views.GoogleRoutesProvider", side_effect=RouteConfigurationError)
    def test_route_api_reports_missing_google_key(self, provider_class):
        incident, _ = self.prepare_incident_for_route()
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/route/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(IncidentRoute.objects.count(), 0)

    @patch("apps.incidents.views.GoogleRoutesProvider")
    def test_route_api_rejects_stale_patient_location(self, provider_class):
        incident, _ = self.prepare_incident_for_route(patient_location_age_minutes=8)
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/route/")

        self.assertEqual(response.status_code, 400)
        provider_class.assert_not_called()

    @patch("apps.incidents.views.GoogleRoutesProvider")
    def test_route_api_rejects_stale_vehicle_location(self, provider_class):
        incident, _ = self.prepare_incident_for_route(vehicle_location_age_minutes=8)
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/route/")

        self.assertEqual(response.status_code, 400)
        provider_class.assert_not_called()

    @patch("apps.incidents.views.GoogleRoutesProvider")
    def test_simulated_route_is_labeled(self, provider_class):
        incident, _ = self.prepare_incident_for_route(simulated=True)
        provider_class.return_value.calculate_driving_route.return_value = RouteResult(
            distance_meters=1000,
            duration_seconds=300,
            encoded_polyline="simulated-polyline",
        )
        self.client.force_authenticate(self.coordinator)

        response = self.client.post(f"/api/v1/incidents/{incident.pk}/route/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_simulated"])

    @patch("apps.incidents.views.GoogleRoutesProvider")
    def test_local_sos_acceptance_flow_keeps_delivery_and_dispatch_evidence_distinct(self, provider_class):
        contact = EmergencyContact.objects.create(
            patient=self.patient,
            name="Acceptance Test Contact",
            phone_number="+233200000099",
            priority_order=1,
            verification_status=EmergencyContact.VerificationStatus.VERIFIED,
        )
        ConsentRecord.objects.create(
            patient=self.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
            status=ConsentRecord.Status.GRANTED,
            policy_version="acceptance-test-v1",
        )
        location_time = timezone.now()
        PatientLocation.objects.create(
            patient=self.patient,
            event_id=uuid.uuid4(),
            latitude=Decimal("5.603700"),
            longitude=Decimal("-0.187000"),
            source=PatientLocation.Source.PHONE,
            quality=PatientLocation.Quality.VALID,
            recorded_at=location_time,
            received_at=location_time,
        )
        self.client.force_authenticate(self.patient_user)
        sos = self.client.post(
            "/api/v1/incidents/sos/",
            {
                "patient": str(self.patient.pk),
                "event_id": str(uuid.uuid4()),
                "trigger_source": Incident.Source.MANUAL,
            },
            format="json",
        )
        self.assertEqual(sos.status_code, 201)
        incident_id = sos.json()["id"]
        self.assertFalse(sos.json()["location"]["is_stale"])

        notification = IncidentNotification.objects.get(incident_id=incident_id)
        self.assertEqual(notification.emergency_contact, contact)
        self.assertEqual(notification.status, IncidentNotification.Status.QUEUED)

        self.client.force_authenticate(self.coordinator)
        base_url = f"/api/v1/incidents/{incident_id}/"
        self.assertEqual(self.client.post(f"{base_url}acknowledge/").status_code, 200)
        vehicle = self.create_vehicle(simulated=True)
        assignment = self.client.post(
            f"{base_url}assign-responder/",
            {"vehicle": str(vehicle.pk), "include_simulated": True},
            format="json",
        )
        self.assertEqual(assignment.status_code, 200)
        self.assertTrue(assignment.json()["is_simulated_dispatch"])

        provider_class.return_value.calculate_driving_route.return_value = RouteResult(
            distance_meters=1200,
            duration_seconds=360,
            encoded_polyline="acceptance-polyline",
        )
        route = self.client.post(f"{base_url}route/")
        self.assertEqual(route.status_code, 200)
        self.assertTrue(route.json()["is_simulated"])

        dispatch_request = self.client.post(f"{base_url}record-dispatch-request/")
        self.assertEqual(dispatch_request.status_code, 200)
        self.assertFalse(dispatch_request.json()["provider_contacted_by_system"])
        confirmation = self.client.post(
            f"{base_url}record-dispatch-confirmation/",
            {"confirmation_reference": "local acceptance test only"},
            format="json",
        )
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(confirmation.json()["confirmation_source"], "operator_reported")

        for next_status in (
            Incident.Status.RESPONDER_EN_ROUTE,
            Incident.Status.ARRIVED,
            Incident.Status.RESOLVED,
            Incident.Status.CLOSED,
        ):
            response = self.client.post(
                f"{base_url}status/",
                {"status": next_status},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.json())
        incident = Incident.objects.get(pk=incident_id)
        self.assertEqual(incident.status, Incident.Status.CLOSED)
        self.assertTrue(incident.is_simulated_dispatch)
        notification.refresh_from_db()
        self.assertEqual(notification.status, IncidentNotification.Status.QUEUED)