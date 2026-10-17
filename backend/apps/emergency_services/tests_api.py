from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile
from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider


class EmergencyDirectoryApiTests(TestCase):
    def setUp(self):
        self.provider = EmergencyProvider.objects.create(
            name="Verified Pilot Provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=EmergencyProvider.VerificationStatus.VERIFIED,
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