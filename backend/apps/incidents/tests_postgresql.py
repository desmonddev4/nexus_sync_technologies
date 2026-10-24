"""PostgreSQL-only concurrency acceptance checks for cross-request races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile
from apps.devices.models import Device
from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider
from apps.incidents.models import Incident
from apps.incidents.services import InvalidResponderAssignment, assign_responder
from apps.patients.models import Patient


@skipUnless(connection.vendor == "postgresql", "Concurrency behavior requires PostgreSQL row locks.")
class PostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.operator = user_model.objects.create_user(username="concurrent-operator")
        AccountProfile.objects.create(
            user=self.operator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )
        self.patient = Patient.objects.create(full_name="Concurrency Test Patient")

    def test_concurrent_duplicate_device_registration_creates_one_device(self):
        barrier = Barrier(2)
        payload = {
            "device_identifier": "NS-CONCURRENT-001",
            "device_type": Device.Type.SIMULATOR,
            "patient": str(self.patient.pk),
            "status": Device.Status.ACTIVE,
        }

        def register_device():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.operator)
                barrier.wait(timeout=10)
                response = client.post("/api/v1/device-registry/", payload, format="json")
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: register_device(), range(2)))

        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(400), 1)
        self.assertEqual(
            Device.objects.filter(device_identifier="NS-CONCURRENT-001").count(),
            1,
        )

    def test_competing_incidents_cannot_claim_the_same_vehicle(self):
        provider = EmergencyProvider.objects.create(
            name="Concurrency Test Provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=EmergencyProvider.VerificationStatus.VERIFIED,
            fleet_feed_authorized=True,
        )
        vehicle = AmbulanceVehicle.objects.create(
            provider=provider,
            vehicle_identifier="NS-CONCURRENT-AMB-001",
            availability=AmbulanceVehicle.Availability.AVAILABLE,
            data_source=AmbulanceVehicle.DataSource.PROVIDER,
            latitude="5.603700",
            longitude="-0.187000",
            location_updated_at=timezone.now(),
        )
        incidents = [
            Incident.objects.create(
                patient=self.patient,
                source_event_id=f"00000000-0000-0000-0000-00000000000{suffix}",
                trigger_source=Incident.Source.MANUAL,
                status=Incident.Status.ACKNOWLEDGED,
            )
            for suffix in (1, 2)
        ]
        barrier = Barrier(2)

        def assign(incident_id):
            close_old_connections()
            try:
                incident = Incident.objects.get(pk=incident_id)
                selected_vehicle = AmbulanceVehicle.objects.get(pk=vehicle.pk)
                actor = get_user_model().objects.get(pk=self.operator.pk)
                barrier.wait(timeout=10)
                try:
                    assign_responder(
                        incident=incident,
                        vehicle=selected_vehicle,
                        actor=actor,
                    )
                    return "assigned"
                except InvalidResponderAssignment:
                    return "unavailable"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(assign, [incident.pk for incident in incidents]))

        self.assertCountEqual(outcomes, ["assigned", "unavailable"])
        vehicle.refresh_from_db()
        self.assertIsNotNone(vehicle.current_incident_id)
        self.assertEqual(
            Incident.objects.filter(assigned_vehicle=vehicle).count(),
            1,
        )
