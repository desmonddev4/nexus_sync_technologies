from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider


class Command(BaseCommand):
    help = "Create clearly labeled simulated ambulance data near UPSA for development."

    def handle(self, *args, **options):
        provider, _ = EmergencyProvider.objects.update_or_create(
            name="Nexus Sync UPSA Simulation Fleet",
            defaults={
                "provider_type": EmergencyProvider.Type.PRIVATE_AMBULANCE,
                "verification_status": EmergencyProvider.VerificationStatus.SIMULATED,
                "verification_source": "Development simulator; not a real provider",
                "coverage_description": "Simulated UPSA development data only",
            },
        )
        vehicle, _ = AmbulanceVehicle.objects.update_or_create(
            provider=provider,
            vehicle_identifier="NS-UPSA-SIM-001",
            defaults={
                "capabilities": ["basic_life_support"],
                "availability": AmbulanceVehicle.Availability.AVAILABLE,
                "data_source": AmbulanceVehicle.DataSource.SIMULATOR,
                "latitude": "5.603700",
                "longitude": "-0.187000",
                "location_accuracy_meters": 25,
                "location_updated_at": timezone.now(),
                "current_incident": None,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded simulated-only provider {provider.name} and vehicle {vehicle.vehicle_identifier}."
            )
        )