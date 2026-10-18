from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel


class IncidentNotification(UUIDTimestampedModel):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        SUBMITTED = "submitted", "Submitted"
        SUBMISSION_UNKNOWN = "submission_unknown", "Submission outcome unknown"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"

    incident = models.ForeignKey(
        "incidents.Incident",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    emergency_contact = models.ForeignKey(
        "patients.EmergencyContact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incident_notifications",
    )
    recipient_address_snapshot = models.CharField(max_length=32)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    provider_task_id = models.CharField(max_length=120, blank=True)
    provider_status_updated_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    provider_name = models.CharField(max_length=40, blank=True)
    provider_message_id = models.CharField(max_length=120, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("incident", "emergency_contact", "channel"),
                name="uniq_incident_contact_notification_channel",
            )
        ]
        indexes = [models.Index(fields=("status", "next_attempt_at"))]

    def __str__(self):
        return f"{self.incident_id}: {self.channel} {self.status}"


class NotificationEvent(UUIDTimestampedModel):
    notification = models.ForeignKey(
        IncidentNotification,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=24, choices=IncidentNotification.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notification_events",
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)


class EscalationPolicy(UUIDTimestampedModel):
    singleton_key = models.CharField(max_length=32, unique=True, default="default")
    initial_notification_timeout_minutes = models.PositiveSmallIntegerField(default=5)
    retry_interval_minutes = models.PositiveSmallIntegerField(default=3)
    max_retry_attempts = models.PositiveSmallIntegerField(default=3)
    escalate_to_coordinator_after_minutes = models.PositiveSmallIntegerField(default=10)
    require_operator_acknowledgement = models.BooleanField(default=True)
    allow_simulation_escalation = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_escalation_policies",
    )

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return "Escalation policy"