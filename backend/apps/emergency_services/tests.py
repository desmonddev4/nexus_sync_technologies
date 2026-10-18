from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider, HealthcareFacility
from apps.emergency_services.services import eligible_vehicles
from apps.emergency_services.routing import (
    GoogleRoutesProvider,
    RouteCalculationError,
    RouteConfigurationError,
)


class EmergencyDirectoryTests(TestCase):
    def setUp(self):
        self.provider = EmergencyProvider.objects.create(
            name="Pilot Ambulance Provider",
            provider_type=EmergencyProvider.Type.PRIVATE_AMBULANCE,
            verification_status=EmergencyProvider.VerificationStatus.VERIFIED,
            fleet_feed_authorized=True,
        )
        self.now = timezone.now()

    def create_vehicle(self, identifier, **overrides):
        values = {
            "provider": self.provider,
            "vehicle_identifier": identifier,
            "availability": AmbulanceVehicle.Availability.AVAILABLE,
            "data_source": AmbulanceVehicle.DataSource.PROVIDER,
            "latitude": Decimal("5.6037"),
            "longitude": Decimal("-0.1870"),
            "location_updated_at": self.now,
        }
        values.update(overrides)
        return AmbulanceVehicle.objects.create(**values)

    def test_eligible_vehicles_require_verified_available_and_fresh_data(self):
        fresh = self.create_vehicle("NS-001", capabilities=["basic_life_support"])
        self.create_vehicle("NS-002", availability=AmbulanceVehicle.Availability.ON_CALL)
        self.create_vehicle(
            "NS-003",
            location_updated_at=self.now - timedelta(minutes=10),
        )
        self.create_vehicle(
            "NS-004",
            current_incident_id=None,
            data_source=AmbulanceVehicle.DataSource.SIMULATOR,
        )
        self.create_vehicle(
            "NS-005",
            capabilities=["advanced_life_support"],
        )

        results = eligible_vehicles(
            latitude=5.6037,
            longitude=-0.1870,
            required_capability="basic_life_support",
            now=self.now,
        )

        self.assertEqual([vehicle for vehicle, _ in results], [fresh])
        self.assertEqual(results[0][1], 0)

    def test_unverified_provider_vehicles_are_not_eligible(self):
        self.create_vehicle("NS-UNVERIFIED")
        self.provider.verification_status = EmergencyProvider.VerificationStatus.UNVERIFIED
        self.provider.save(update_fields=("verification_status", "updated_at"))

        results = eligible_vehicles(
            latitude=5.6037,
            longitude=-0.1870,
            now=self.now,
        )

        self.assertEqual(results, [])

    def test_simulated_vehicles_require_explicit_opt_in(self):
        self.provider.verification_status = EmergencyProvider.VerificationStatus.SIMULATED
        self.provider.save(update_fields=("verification_status", "updated_at"))
        simulated = self.create_vehicle(
            "NS-SIM-001",
            data_source=AmbulanceVehicle.DataSource.SIMULATOR,
        )

        excluded = eligible_vehicles(latitude=5.6, longitude=-0.18, now=self.now)
        included = eligible_vehicles(
            latitude=5.6,
            longitude=-0.18,
            include_simulated=True,
            now=self.now,
        )

        self.assertEqual(excluded, [])
        self.assertEqual(included[0][0], simulated)

    def test_facility_coordinates_are_validated(self):
        facility = HealthcareFacility(
            name="Test Clinic",
            facility_type=HealthcareFacility.Type.CLINIC,
            latitude=Decimal("91"),
            longitude=Decimal("-0.1"),
        )

        with self.assertRaises(ValidationError):
            facility.full_clean()


class GoogleRoutesProviderTests(TestCase):
    @override_settings(GOOGLE_MAPS_API_KEY="google-test-key")
    def test_requests_traffic_aware_driving_route_and_parses_eta(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "routes": [
                {
                    "distanceMeters": 3400,
                    "duration": "725s",
                    "polyline": {"encodedPolyline": "encoded-route"},
                }
            ]
        }
        session = Mock()
        session.post.return_value = response
        provider = GoogleRoutesProvider(session=session)

        result = provider.calculate_driving_route(
            origin=(Decimal("5.60"), Decimal("-0.18")),
            destination=(Decimal("5.61"), Decimal("-0.19")),
        )

        self.assertEqual(result.distance_meters, 3400)
        self.assertEqual(result.duration_seconds, 725)
        self.assertEqual(result.encoded_polyline, "encoded-route")
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], GoogleRoutesProvider.endpoint)
        self.assertEqual(kwargs["headers"]["X-Goog-Api-Key"], "google-test-key")
        self.assertEqual(kwargs["headers"]["X-Goog-FieldMask"], GoogleRoutesProvider.field_mask)
        self.assertEqual(kwargs["json"]["routingPreference"], "TRAFFIC_AWARE")
        self.assertEqual(kwargs["json"]["origin"]["location"]["latLng"]["latitude"], 5.6)

    @override_settings(GOOGLE_MAPS_API_KEY="")
    def test_requires_a_google_routes_api_key(self):
        with self.assertRaises(RouteConfigurationError):
            GoogleRoutesProvider()

    @override_settings(GOOGLE_MAPS_API_KEY="google-test-key")
    def test_invalid_google_response_is_not_treated_as_a_route(self):
        response = Mock(status_code=200)
        response.json.return_value = {"routes": []}
        session = Mock()
        session.post.return_value = response
        provider = GoogleRoutesProvider(session=session)

        with self.assertRaises(RouteCalculationError):
            provider.calculate_driving_route(
                origin=(5.6, -0.18),
                destination=(5.61, -0.19),
            )