from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel


class AuditLog(UUIDTimestampedModel):
    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        DENIED = "denied", "Denied"
        FAILURE = "failure", "Failure"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=64, blank=True)
    outcome = models.CharField(
        max_length=12,
        choices=Outcome.choices,
        default=Outcome.SUCCESS,
    )
    http_method = models.CharField(max_length=8, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("resource_type", "resource_id", "-created_at")),
            models.Index(fields=("actor", "-created_at")),
        ]

    def __str__(self):
        return f"{self.action} {self.resource_type}:{self.resource_id} ({self.outcome})"