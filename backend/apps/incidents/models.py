from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel
from apps.emergency_services.models import AmbulanceVehicle
from apps.monitoring.models import PatientLocation
from apps.patients.models import Patient


class Incident(UUIDTimestampedModel):
    class Type(models.TextChoices):
        MANUAL_SOS = "manual_sos", "Manual SOS"
        SUSPECTED_FALL = "suspected_fall", "Suspected fall"
        MEASUREMENT_ALERT = "measurement_alert", "Measurement alert"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        WEARABLE = "wearable", "Wearable"
        SIMULATOR = "simulator", "Simulator"
        RULE = "rule", "Safety rule"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESPONDER_ASSIGNED = "responder_assigned", "Responder assigned"
        DISPATCH_REQUESTED = "dispatch_requested", "Dispatch requested"
        DISPATCH_CONFIRMED = "dispatch_confirmed", "Dispatch confirmed"
        RESPONDER_EN_ROUTE = "responder_en_route", "Responder en route"
        ARRIVED = "arrived", "Arrived"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    source_event_id = models.UUIDField()
    incident_type = models.CharField(
        max_length=32,
        choices=Type.choices,
        default=Type.MANUAL_SOS,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.HIGH,
    )
    trigger_source = models.CharField(max_length=16, choices=Source.choices)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.CREATED,
    )
    assigned_vehicle = models.ForeignKey(
        AmbulanceVehicle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_incidents",
    )
    assigned_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_incidents",
    )
    is_simulated_dispatch = models.BooleanField(default=False)
    dispatch_requested_at = models.DateTimeField(null=True, blank=True)
    dispatch_confirmed_at = models.DateTimeField(null=True, blank=True)
    dispatch_confirmation_reference = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "source_event_id"),
                name="uniq_patient_incident_source_event",
            )
        ]

    def __str__(self):
        return f"{self.incident_type} for {self.patient_id} ({self.status})"


class IncidentEvent(UUIDTimestampedModel):
    class Type(models.TextChoices):
        CREATED = "created", "Created"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        STATUS_CHANGED = "status_changed", "Status changed"
        RESPONDER_ASSIGNED = "responder_assigned", "Responder assigned"
        DISPATCH_REQUEST_RECORDED = "dispatch_request_recorded", "Dispatch request recorded"
        DISPATCH_CONFIRMATION_RECORDED = "dispatch_confirmation_recorded", "Dispatch confirmation recorded"
        EVIDENCE_RECORDED = "evidence_recorded", "Measurement evidence recorded"

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=40, choices=Type.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incident_events",
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.incident_id}: {self.event_type}"


class IncidentLocationSnapshot(UUIDTimestampedModel):
    incident = models.OneToOneField(
        Incident,
        on_delete=models.CASCADE,
        related_name="location_snapshot",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=16, choices=PatientLocation.Source.choices)
    quality = models.CharField(max_length=16, choices=PatientLocation.Quality.choices)
    recorded_at = models.DateTimeField()
    received_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=("recorded_at", "received_at"))]


class IncidentRoute(UUIDTimestampedModel):
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="route_estimates",
    )
    vehicle = models.ForeignKey(
        AmbulanceVehicle,
        null=True,
        on_delete=models.SET_NULL,
        related_name="route_estimates",
    )
    routing_provider = models.CharField(max_length=32, default="google_routes")
    origin_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    origin_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    distance_meters = models.PositiveIntegerField()
    duration_seconds = models.PositiveIntegerField()
    encoded_polyline = models.TextField(blank=True)
    is_simulated = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)