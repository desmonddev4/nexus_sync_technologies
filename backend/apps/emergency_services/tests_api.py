from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditLog
from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider


class EmergencyDirectoryApiTests(TestCase):
    def setUp(self):
        self.provider = EmergencyProvider.objects.create(
            name="Verified Pilot Provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=EmergencyProvider.VerificationStatus.VERIFIED,
            fleet_feed_authorized=True,
            dispatch_phone_number="+233200000000",
        )
        self.vehicle = AmbulanceVehicle.objects.create(
            provider=self.provider,
            vehicle_identifier="NS-PILOT-001",
            availability=AmbulanceVehicle.Availability.AVAILABLE,
            data_source=AmbulanceVehicle.DataSource.SIMULATOR,
            latitude=Decimal("5.6037"),
            longitude=Decimal("-0.1870"),
            location_updated_at=timezone.now(),
        )
        self.coordinator = get_user_model().objects.create_user(username="dispatch")
        AccountProfile.objects.create(
            user=self.coordinator,
            role=AccountProfile.Role.EMERGENCY_COORDINATOR,
        )

    def test_directory_requires_staff_authentication(self):
        response = APIClient().get("/api/v1/providers/")

        self.assertEqual(response.status_code, 401)

    def test_staff_can_list_verified_providers(self):
        client = APIClient()
        client.force_authenticate(self.coordinator)

        response = client.get("/api/v1/providers/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["dispatch_phone_number"], "+233200000000")
        self.assertTrue(response.json()[0]["fleet_feed_authorized"])

    def test_coordinator_can_create_unverified_provider_then_verify_with_source(self):
        client = APIClient()
        client.force_authenticate(self.coordinator)
        created = client.post(
            "/api/v1/directory/providers/",
            {
                "name": "New Accra Provider",
                "provider_type": EmergencyProvider.Type.PRIVATE_AMBULANCE,
                "dispatch_phone_number": "+233201234567",
                "latitude": "5.600000",
                "longitude": "-0.180000",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        provider_id = created.json()["id"]
        self.assertEqual(created.json()["verification_status"], "unverified")
        self.assertFalse(EmergencyProvider.objects.get(pk=provider_id).fleet_feed_authorized)

        verified = client.post(
            f"/api/v1/directory/providers/{provider_id}/verify/",
            {"verification_source": "Provider dispatch office confirmed by phone, 2026-10-19"},
            format="json",
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["verification_status"], "verified")
        self.assertEqual(verified.json()["verified_by"], self.coordinator.username)
        self.assertTrue(AuditLog.objects.filter(action="directory.provider.verified", resource_id=provider_id).exists())
        self.assertEqual(len(client.get("/api/v1/providers/").json()), 2)

    def test_clinician_cannot_modify_directory(self):
        clinician = get_user_model().objects.create_user(username="directory-clinician")
        AccountProfile.objects.create(user=clinician, role=AccountProfile.Role.CLINICIAN)
        client = APIClient()
        client.force_authenticate(clinician)

        response = client.post(
            "/api/v1/directory/facilities/",
            {
                "name": "Unapproved Clinic",
                "facility_type": "clinic",
                "latitude": "5.600000",
                "longitude": "-0.180000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_provider_vehicle_creation_requires_authorized_verified_feed(self):
        self.provider.fleet_feed_authorized = False
        self.provider.save(update_fields=("fleet_feed_authorized", "updated_at"))
        client = APIClient()
        client.force_authenticate(self.coordinator)

        response = client.post(
            "/api/v1/directory/vehicles/",
            {
                "provider": str(self.provider.pk),
                "vehicle_identifier": "UNAUTHORIZED-LIVE-01",
                "data_source": AmbulanceVehicle.DataSource.PROVIDER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AmbulanceVehicle.objects.filter(vehicle_identifier="UNAUTHORIZED-LIVE-01").exists())

    def test_simulated_vehicle_creation_requires_simulation_provider_and_unavailable_status(self):
        client = APIClient()
        client.force_authenticate(self.coordinator)

        wrong_provider = client.post(
            "/api/v1/directory/vehicles/",
            {
                "provider": str(self.provider.pk),
                "vehicle_identifier": "SIM-ON-LIVE-PROVIDER",
                "data_source": AmbulanceVehicle.DataSource.SIMULATOR,
                "availability": AmbulanceVehicle.Availability.UNAVAILABLE,
            },
            format="json",
        )
        self.assertEqual(wrong_provider.status_code, 400)

        simulated_provider = EmergencyProvider.objects.create(
            name="Simulation-only provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=EmergencyProvider.VerificationStatus.SIMULATED,
        )
        marked_available = client.post(
            "/api/v1/directory/vehicles/",
            {
                "provider": str(simulated_provider.pk),
                "vehicle_identifier": "SIM-MUST-STAY-UNAVAILABLE",
                "data_source": AmbulanceVehicle.DataSource.SIMULATOR,
                "availability": AmbulanceVehicle.Availability.AVAILABLE,
            },
            format="json",
        )
        self.assertEqual(marked_available.status_code, 400)
        self.assertFalse(AmbulanceVehicle.objects.filter(vehicle_identifier__startswith="SIM-").exists())

        created = client.post(
            "/api/v1/directory/vehicles/",
            {
                "provider": str(simulated_provider.pk),
                "vehicle_identifier": "SIM-SAFE-001",
                "data_source": AmbulanceVehicle.DataSource.SIMULATOR,
                "availability": AmbulanceVehicle.Availability.UNAVAILABLE,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["availability"], AmbulanceVehicle.Availability.UNAVAILABLE)

    def test_unverified_facility_is_not_visible_in_operational_directory(self):
        from apps.emergency_services.models import HealthcareFacility

        facility = HealthcareFacility.objects.create(
            name="Pending Clinic",
            facility_type=HealthcareFacility.Type.CLINIC,
            address="Madina",
            latitude=Decimal("5.600000"),
            longitude=Decimal("-0.180000"),
        )
        client = APIClient()
        client.force_authenticate(self.coordinator)

        pending = client.get("/api/v1/directory/facilities/")
        operational = client.get("/api/v1/facilities/")

        self.assertEqual(pending.status_code, 200)
        self.assertTrue(any(row["id"] == str(facility.pk) for row in pending.json()))
        self.assertEqual(operational.json(), [])

    def test_nearby_api_excludes_simulation_until_explicitly_requested(self):
        self.provider.verification_status = EmergencyProvider.VerificationStatus.SIMULATED
        self.provider.save(update_fields=("verification_status", "updated_at"))
        client = APIClient()
        client.force_authenticate(self.coordinator)
        query = "latitude=5.6037&longitude=-0.1870"

        hidden = client.get(f"/api/v1/vehicles/nearby/?{query}")
        included = client.get(f"/api/v1/vehicles/nearby/?{query}&include_simulated=true")

        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json(), [])
        self.assertEqual(included.status_code, 200)
        self.assertEqual(len(included.json()), 1)
        self.assertTrue(included.json()[0]["is_simulated"])
        self.assertEqual(included.json()[0]["distance_kilometers"], 0)

    def test_nearby_api_excludes_provider_feed_when_not_authorized(self):
        self.vehicle.data_source = AmbulanceVehicle.DataSource.PROVIDER
        self.vehicle.save(update_fields=("data_source", "updated_at"))
        self.provider.fleet_feed_authorized = False
        self.provider.save(update_fields=("fleet_feed_authorized", "updated_at"))
        client = APIClient()
        client.force_authenticate(self.coordinator)

        response = client.get("/api/v1/vehicles/nearby/?latitude=5.6037&longitude=-0.1870")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_invalid_coordinates_are_rejected(self):
        client = APIClient()
        client.force_authenticate(self.coordinator)

        response = client.get("/api/v1/vehicles/nearby/?latitude=91&longitude=0")

        self.assertEqual(response.status_code, 400)

    def test_upsa_simulation_seed_is_idempotent_and_not_a_verified_provider(self):
        call_command("seed_upsa_simulation", stdout=StringIO())
        call_command("seed_upsa_simulation", stdout=StringIO())

        provider = EmergencyProvider.objects.get(name="Nexus Sync UPSA Simulation Fleet")
        vehicle = provider.vehicles.get(vehicle_identifier="NS-UPSA-SIM-001")
        self.assertEqual(provider.verification_status, EmergencyProvider.VerificationStatus.SIMULATED)
        self.assertEqual(provider.vehicles.count(), 1)
        self.assertEqual(vehicle.data_source, AmbulanceVehicle.DataSource.SIMULATOR)