from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from django.db.models import Q
from django.utils import timezone

from .models import AmbulanceVehicle, EmergencyProvider


def distance_kilometers(latitude_a, longitude_a, latitude_b, longitude_b):
    latitude_a, longitude_a, latitude_b, longitude_b = map(
        radians,
        (float(latitude_a), float(longitude_a), float(latitude_b), float(longitude_b)),
    )
    latitude_delta = latitude_b - latitude_a
    longitude_delta = longitude_b - longitude_a
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(latitude_a) * cos(latitude_b) * sin(longitude_delta / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(haversine))


def eligible_vehicles(
    *,
    latitude,
    longitude,
    max_location_age_seconds=300,
    max_distance_kilometers=None,
    required_capability=None,
    include_simulated=False,
    now=None,
):
    now = now or timezone.now()
    newest_acceptable_location = now - timedelta(seconds=max_location_age_seconds)
    provider_statuses = [EmergencyProvider.VerificationStatus.VERIFIED]
    if include_simulated:
        provider_statuses.append(EmergencyProvider.VerificationStatus.SIMULATED)
    vehicles = AmbulanceVehicle.objects.select_related("provider").filter(
        provider__verification_status__in=provider_statuses,
        availability=AmbulanceVehicle.Availability.AVAILABLE,
        latitude__isnull=False,
        longitude__isnull=False,
        location_updated_at__gte=newest_acceptable_location,
        current_incident__isnull=True,
    )
    if not include_simulated:
        vehicles = vehicles.filter(
            data_source=AmbulanceVehicle.DataSource.PROVIDER,
            provider__fleet_feed_authorized=True,
        )
    else:
        vehicles = vehicles.filter(
            Q(
                data_source=AmbulanceVehicle.DataSource.PROVIDER,
                provider__fleet_feed_authorized=True,
            )
            | Q(
                data_source=AmbulanceVehicle.DataSource.SIMULATOR,
                provider__verification_status=EmergencyProvider.VerificationStatus.SIMULATED,
            )
        )

    results = []
    for vehicle in vehicles:
        if required_capability and required_capability not in vehicle.capabilities:
            continue
        distance = distance_kilometers(latitude, longitude, vehicle.latitude, vehicle.longitude)
        if max_distance_kilometers is not None and distance > max_distance_kilometers:
            continue
        results.append((vehicle, distance))
    return sorted(results, key=lambda item: item[1])