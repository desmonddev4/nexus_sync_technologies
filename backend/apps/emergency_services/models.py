from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimestampedModel


class EmergencyProvider(UUIDTimestampedModel):
    class Type(models.TextChoices):
        NATIONAL_AMBULANCE = "national_ambulance", "National ambulance service"
        PRIVATE_AMBULANCE = "private_ambulance", "Private ambulance service"

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"
        SIMULATED = "simulated", "Simulation only"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=200)
    provider_type = models.CharField(max_length=32, choices=Type.choices)
    dispatch_phone_number = models.CharField(max_length=32, blank=True)
    general_phone_number = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    operating_hours = models.JSONField(default=dict, blank=True)
    coverage_description = models.TextField(blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    verification_source = models.CharField(max_length=300, blank=True)
    verified_by = models.CharField(max_length=160, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class HealthcareFacility(UUIDTimestampedModel):
    class Type(models.TextChoices):
        HOSPITAL = "hospital", "Hospital"
        CLINIC = "clinic", "Clinic"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=200)
    facility_type = models.CharField(max_length=16, choices=Type.choices)
    address = models.CharField(max_length=300, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    verification_source = models.CharField(max_length=300, blank=True)
    verified_by = models.CharField(max_length=160, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="facility_latitude_in_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="facility_longitude_in_range",
            ),
        ]

    def __str__(self):
        return self.name


class AmbulanceVehicle(UUIDTimestampedModel):
    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNAVAILABLE = "unavailable", "Unavailable"
        ON_CALL = "on_call", "On call"
        OUT_OF_SERVICE = "out_of_service", "Out of service"

    class DataSource(models.TextChoices):
        SIMULATOR = "simulator", "Simulator"
        PROVIDER = "provider", "Provider feed"

    provider = models.ForeignKey(
        EmergencyProvider,
        on_delete=models.PROTECT,
        related_name="vehicles",
    )
    vehicle_identifier = models.CharField(max_length=80)
    capabilities = models.JSONField(default=list, blank=True)
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.UNAVAILABLE,
    )
    data_source = models.CharField(max_length=16, choices=DataSource.choices)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    location_accuracy_meters = models.PositiveIntegerField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    current_incident = models.ForeignKey(
        "incidents.Incident",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_vehicles",
    )

    class Meta:
        ordering = ("provider__name", "vehicle_identifier")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "vehicle_identifier"),
                name="uniq_provider_vehicle_identifier",
            ),
            models.CheckConstraint(
                condition=(Q(latitude__isnull=True) & Q(longitude__isnull=True))
                | (Q(latitude__isnull=False) & Q(longitude__isnull=False)),
                name="vehicle_coordinates_set_together",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True)
                | (Q(latitude__gte=-90) & Q(latitude__lte=90)),
                name="vehicle_latitude_in_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True)
                | (Q(longitude__gte=-180) & Q(longitude__lte=180)),
                name="vehicle_longitude_in_range",
            ),
        ]

    def __str__(self):
        return f"{self.provider}: {self.vehicle_identifier}"