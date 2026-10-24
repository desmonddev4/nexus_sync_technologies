from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import UUIDTimestampedModel


class Patient(UUIDTimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    relevant_medical_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ("full_name",)

    def __str__(self):
        return self.full_name


class EmergencyContact(UUIDTimestampedModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="emergency_contacts",
    )
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=80, blank=True)
    phone_number = models.CharField(max_length=32)
    notification_preferences = models.JSONField(default=dict, blank=True)
    priority_order = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )

    class Meta:
        ordering = ("priority_order",)
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "priority_order"),
                name="uniq_patient_contact_priority",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.patient_id})"


class ConsentRecord(UUIDTimestampedModel):
    class Scope(models.TextChoices):
        HEALTH_MONITORING = "health_monitoring", "Health monitoring"
        LOCATION_SHARING = "location_sharing", "Location sharing"
        EMERGENCY_CONTACTS = "emergency_contacts", "Emergency contacts"

    class Status(models.TextChoices):
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )
    scope = models.CharField(max_length=32, choices=Scope.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    policy_version = models.CharField(max_length=40)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_patient_consents",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [models.Index(fields=("patient", "scope", "-recorded_at"))]

    def __str__(self):
        return f"{self.patient_id}: {self.scope} {self.status}"



class PatientAccessGrant(UUIDTimestampedModel):
    class Scope(models.TextChoices):
        PATIENT = "patient", "Basic patient profile"
        HEALTH = "health", "Measurements and health readings"
        DEVICES = "devices", "Connected devices"
        LOCATION = "location", "Patient locations"
        INCIDENTS = "incidents", "Incident history and notification status"
        SOS = "sos", "Raise SOS incidents"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="access_grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_access_grants")
    scopes = models.JSONField(default=list)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="granted_patient_access")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("user__username",)
        constraints = [models.UniqueConstraint(fields=("patient", "user"), name="uniq_patient_user_access_grant")]
        indexes = [models.Index(fields=("user", "revoked_at"))]

    def __str__(self):
        return f"{self.user_id} access to {self.patient_id}"

class PatientDataRequest(UUIDTimestampedModel):
    class RequestType(models.TextChoices):
        ACCESS_EXPORT = "access_export", "Access export"
        DELETION = "deletion", "Deletion"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FULFILLED = "fulfilled", "Fulfilled"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="data_requests",
    )
    request_type = models.CharField(max_length=24, choices=RequestType.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_data_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_patient_data_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_patient_data_requests",
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    fulfillment_summary = models.JSONField(default=dict, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)
        indexes = [models.Index(fields=("patient", "status", "requested_at"))]

    def __str__(self):
        return f"{self.patient_id}: {self.request_type} {self.status}"
