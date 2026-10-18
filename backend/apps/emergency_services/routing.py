from dataclasses import dataclass
import re

import requests
from django.conf import settings


class RouteConfigurationError(Exception):
    pass


class RouteCalculationError(Exception):
    pass


@dataclass(frozen=True)
class RouteResult:
    distance_meters: int
    duration_seconds: int
    encoded_polyline: str


class GoogleRoutesProvider:
    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"
    field_mask = "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"

    def __init__(self, *, api_key=None, session=None):
        self.api_key = api_key if api_key is not None else settings.GOOGLE_MAPS_API_KEY
        self.session = session or requests
        if not self.api_key:
            raise RouteConfigurationError("GOOGLE_MAPS_API_KEY is not configured.")

    def calculate_driving_route(self, *, origin, destination):
        payload = {
            "origin": {"location": {"latLng": self._lat_lng(origin)}},
            "destination": {"location": {"latLng": self._lat_lng(destination)}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "languageCode": "en",
            "units": "METRIC",
        }
        try:
            response = self.session.post(
                self.endpoint,
                headers={
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": self.field_mask,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
        except requests.RequestException as error:
            raise RouteCalculationError("Google Routes API could not be reached.") from error
        if response.status_code >= 400:
            raise RouteCalculationError(
                f"Google Routes API returned HTTP {response.status_code}."
            )
        try:
            route = response.json()["routes"][0]
            duration = route["duration"]
            duration_match = re.fullmatch(r"(\d+(?:\.\d+)?)s", duration)
            if not duration_match:
                raise ValueError("Unsupported route duration format.")
            return RouteResult(
                distance_meters=int(route["distanceMeters"]),
                duration_seconds=int(float(duration_match.group(1))),
                encoded_polyline=route.get("polyline", {}).get("encodedPolyline", ""),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RouteCalculationError("Google Routes API returned an invalid route.") from error

    @staticmethod
    def _lat_lng(coordinates):
        latitude, longitude = coordinates
        return {"latitude": float(latitude), "longitude": float(longitude)}