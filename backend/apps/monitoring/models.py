from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimestampedModel
from apps.devices.models import Device
from apps.patients.models import Patient


class Measurement(UUIDTimestampedModel):
    class Type(models.TextChoices):
        HEART_RATE = "heart_rate_bpm", "Heart rate"
        SPO2 = "spo2_percent", "SpO2"
        SKIN_TEMPERATURE = "skin_temperature_celsius", "Skin temperature"
        BODY_TEMPERATURE = "body_temperature_celsius", "Body temperature"
        SYSTOLIC_BLOOD_PRESSURE = "systolic_bp_mmhg", "Systolic blood pressure"
        DIASTOLIC_BLOOD_PRESSURE = "diastolic_bp_mmhg", "Diastolic blood pressure"

    class Source(models.TextChoices):
        WEARABLE = "wearable", "Wearable"
        SIMULATOR = "simulator", "Simulator"
        MANUAL = "manual", "Manual entry"
        VALIDATED_EXTERNAL = "validated_external", "Validated external device"

    class Quality(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        ACCEPTABLE = "acceptable", "Acceptable"
        QUESTIONABLE = "questionable", "Questionable"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="measurements",
    )
    device = models.ForeignKey(
        Device,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="measurements",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_measurements",
    )
    event_id = models.UUIDField()
    measurement_type = models.CharField(max_length=32, choices=Type.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=24)
    source = models.CharField(max_length=24, choices=Source.choices)
    quality = models.CharField(
        max_length=16,
        choices=Quality.choices,
        default=Quality.UNREVIEWED,
    )
    quality_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_measurements",
    )
    quality_reviewed_at = models.DateTimeField(null=True, blank=True)
    measured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-measured_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "event_id"),
                name="uniq_patient_measurement_event",
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0),
                name="measurement_value_nonnegative",
            ),
            models.CheckConstraint(
                condition=~Q(measurement_type="spo2_percent") | Q(value__lte=100),
                name="spo2_value_lte_100",
            ),
        ]

    def __str__(self):
        return f"{self.patient_id}: {self.measurement_type}={self.value} {self.unit}"


class MonitoringRule(UUIDTimestampedModel):
    class Operator(models.TextChoices):
        GREATER_THAN = "gt", "Greater than"
        GREATER_THAN_OR_EQUAL = "gte", "Greater than or equal"
        LESS_THAN = "lt", "Less than"
        LESS_THAN_OR_EQUAL = "lte", "Less than or equal"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    measurement_type = models.CharField(max_length=32, choices=Measurement.Type.choices)
    operator = models.CharField(max_length=3, choices=Operator.choices)
    threshold = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    priority = models.CharField(max_length=16, choices=Priority.choices)
    minimum_consecutive_readings = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    lookback_window_seconds = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(30), MaxValueValidator(86400)],
    )
    include_simulated = models.BooleanField(default=False)
    version = models.CharField(max_length=40, default="v1")
    is_enabled = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_monitoring_rules",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("name", "version"),
                name="uniq_monitoring_rule_name_version",
            ),
            models.CheckConstraint(
                condition=~Q(is_enabled=True)
                | (Q(reviewed_by__isnull=False) & Q(reviewed_at__isnull=False)),
                name="enabled_monitoring_rule_requires_review",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.version})"


class MonitoringRuleEvaluation(UUIDTimestampedModel):
    class Status(models.TextChoices):
        QUALITY_REJECTED = "quality_rejected", "Quality rejected"
        SIMULATED_SKIPPED = "simulated_skipped", "Simulation skipped"
        STALE_READING = "stale_reading", "Stale reading"
        INSUFFICIENT_READINGS = "insufficient_readings", "Insufficient readings"
        NO_MATCH = "no_match", "No match"
        TRIGGERED = "triggered", "Triggered"
        LINKED_TO_ACTIVE_INCIDENT = "linked_to_active_incident", "Linked to active incident"

    rule = models.ForeignKey(
        MonitoringRule,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.PROTECT,
        related_name="rule_evaluations",
    )
    incident = models.ForeignKey(
        "incidents.Incident",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rule_evaluations",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("rule", "measurement"),
                name="uniq_monitoring_rule_measurement_evaluation",
            )
        ]


class PatientLocation(UUIDTimestampedModel):
    class Source(models.TextChoices):
        WEARABLE = "wearable", "Wearable"
        PHONE = "phone", "Phone"
        SIMULATOR = "simulator", "Simulator"
        OPERATOR = "operator", "Operator entry"

    class Quality(models.TextChoices):
        VALID = "valid", "Valid"
        LOW_ACCURACY = "low_accuracy", "Low accuracy"
        STALE = "stale", "Stale"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="locations",
    )
    device = models.ForeignKey(
        Device,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locations",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_patient_locations",
    )
    event_id = models.UUIDField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices)
    quality = models.CharField(
        max_length=16,
        choices=Quality.choices,
        default=Quality.VALID,
    )
    recorded_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "event_id"),
                name="uniq_patient_location_event",
            ),
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="location_latitude_in_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="location_longitude_in_range",
            ),
            models.CheckConstraint(
                condition=Q(accuracy_meters__isnull=True) | Q(accuracy_meters__gte=0),
                name="location_accuracy_nonnegative",
            ),
        ]